#!/usr/bin/env python3
"""Manage tokens/tokens.yaml — the single source of truth for credentials.

Subcommands (never print secret values):

  migrate       Consolidate credentials from the legacy gitignored .env files
                (root .env + instances/*/.env) into tokens/tokens.yaml.
                Existing tokens.yaml values win; missing keys are added.
                Creates tokens/tokens.yaml.bak-<ts> before writing.

  generate      Produce a fresh tokens/tokens.yaml from tokens.example.yaml,
                generating random 48-hex door secrets for every agent.
                Refuses to overwrite an existing file unless --force.

  rotate-doors  Regenerate ONLY the door secrets (keeps llm/linear/github),
                then remind you to run derive-agents. Use after a leak.

  set <path>    Set one dotted key from a hidden prompt — the value is never
                echoed and never lands in shell history. Use this to install a
                rotated provider key.
                  python3 office/manage_tokens.py set llm.factories.office

  derive-agents Regenerate crew/agents.json (gitignored door registry used by
                crew/crew-send.py) from tokens.yaml doors.office.

  check         Validate tokens.yaml parses and every declared door is set.

Usage:
  python3 office/manage_tokens.py migrate [--dry-run]
  python3 office/manage_tokens.py generate [--force]
  python3 office/manage_tokens.py derive-agents
  python3 office/manage_tokens.py check
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOKENS_PATH = ROOT / "tokens" / "tokens.yaml"
EXAMPLE_PATH = ROOT / "tokens" / "tokens.example.yaml"
REVOKED_PATH = ROOT / "tokens" / "revoked.txt"
AGENTS_PATH = ROOT / "crew" / "agents.json"

sys.path.insert(0, str(HERE))
from credentials import parse_tokens  # noqa: E402

# host door ports for Office agents (docker-compose.yml 8751..8754)
OFFICE_PORTS = {
    "architect": 8751,
    "staff-engineer": 8752,
    "scrum-master": 8753,
    "super-devops": 8754,
}

# legacy .env -> (factory, instance, {ENV_VAR: agent_id})
DOOR_ENV_MAP = [
    (".env", "office", "office", {
        "DOOR_SECRET_ARCHITECT": "architect",
        "DOOR_SECRET_STAFF_ENGINEER": "staff-engineer",
        "DOOR_SECRET_SCRUM_MASTER": "scrum-master",
        "DOOR_SECRET_SUPER_DEVOPS": "super-devops",
    }),
    ("instances/dev-1/.env", "dev-crew", "dev-1", {
        "DOOR_SECRET_DEVELOPER": "developer",
        "DOOR_SECRET_QA": "qa",
        "DOOR_SECRET_TECH_PM": "tech-pm",
        "DOOR_SECRET_DEVOPS": "devops",
    }),
    ("instances/lab-1/.env", "lab-crew", "lab-1", {
        "DOOR_SECRET_RESEARCH_LEAD": "research-lead",
        "DOOR_SECRET_RESEARCH_ENGINEER": "research-engineer",
        "DOOR_SECRET_EVALUATION": "evaluation",
    }),
    ("instances/spec-1/.env", "product-factory", "spec-1", {
        "DOOR_SECRET_TECHNICAL_PRODUCT_MANAGER": "technical-product-manager",
        "DOOR_SECRET_PRODUCT_RESEARCHER": "product-researcher",
        "DOOR_SECRET_SYSTEM_DOMAIN_ANALYST": "system-domain-analyst",
        "DOOR_SECRET_ADVERSARIAL_REVIEWER": "adversarial-reviewer",
    }),
]

LLM_ENV_MAP = [
    (".env", "office"),
    ("instances/dev-1/.env", "dev-crew"),
    ("instances/lab-1/.env", "lab-crew"),
    ("instances/spec-1/.env", "product-factory"),
]


# ---- helpers ---------------------------------------------------------------
def parse_env_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    out: dict = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip("\"'")
        out[k] = v
    return out


def load_tokens() -> dict:
    if TOKENS_PATH.is_file():
        return parse_tokens(TOKENS_PATH.read_text(encoding="utf-8"))
    return {}


def _emit(d: dict, indent: int = 0) -> list[str]:
    lines: list[str] = []
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            lines.extend(_emit(v, indent + 1))
        else:
            lines.append(f'{pad}{k}: "{v}"')
    return lines


def dump_tokens(tokens: dict) -> str:
    header = (
        "# ============================================================================\n"
        "# AGENT-OFFICE SECRETS — SINGLE SOURCE OF TRUTH. GITIGNORED. NEVER COMMIT.\n"
        "# Managed by: python3 office/manage_tokens.py\n"
        "# ============================================================================\n"
    )
    return header + "\n".join(_emit(tokens)) + "\n"


def set_default(tokens: dict, path: list[str], value) -> bool:
    """Set nested key only if currently absent/empty. Returns True if changed."""
    node = tokens
    for key in path[:-1]:
        node = node.setdefault(key, {})
    last = path[-1]
    if node.get(last):
        return False
    node[last] = value
    return True


def backup() -> Path:
    bak = TOKENS_PATH.with_name(f"tokens.yaml.bak-{int(time.time())}")
    if TOKENS_PATH.is_file():
        bak.write_text(TOKENS_PATH.read_text(encoding="utf-8"))
    return bak


def mask(v: str) -> str:
    return f"<set, len={len(v)}>" if v else "<empty>"


# ---- subcommands -----------------------------------------------------------
def cmd_migrate(dry: bool) -> int:
    tokens = load_tokens()
    changed: list[str] = []

    # LLM keys (root .env -> office, instance .env -> its factory)
    for rel, factory in LLM_ENV_MAP:
        env = parse_env_file(ROOT / rel)
        key = env.get("CUSTOM_API_KEY", "")
        if key and set_default(tokens, ["llm", "factories", factory], key):
            changed.append(f"llm.factories.{factory} {mask(key)}")

    # shared
    root_env = parse_env_file(ROOT / ".env")
    if root_env.get("GITHUB_TOKEN") and set_default(
            tokens, ["github", "token"], root_env["GITHUB_TOKEN"]):
        changed.append(f"github.token {mask(root_env['GITHUB_TOKEN'])}")
    if root_env.get("LINEAR_API_KEY") and set_default(
            tokens, ["linear", "api_key"], root_env["LINEAR_API_KEY"]):
        changed.append(f"linear.api_key {mask(root_env['LINEAR_API_KEY'])}")

    # doors
    for rel, _factory, instance, mapping in DOOR_ENV_MAP:
        env = parse_env_file(ROOT / rel)
        for var, agent in mapping.items():
            secret = env.get(var, "")
            if secret and set_default(tokens, ["doors", instance, agent], secret):
                changed.append(f"doors.{instance}.{agent} {mask(secret)}")

    if not changed:
        print("[manage-tokens] migrate: nothing to add (tokens.yaml already complete)")
        return 0

    for c in changed:
        print(f"[manage-tokens] + {c}")
    if dry:
        print(f"[manage-tokens] DRY-RUN: {len(changed)} key(s) would be written to "
              f"{TOKENS_PATH.relative_to(ROOT)}")
        return 0

    bak = backup()
    TOKENS_PATH.write_text(dump_tokens(tokens), encoding="utf-8")
    print(f"[manage-tokens] wrote {TOKENS_PATH.relative_to(ROOT)} "
          f"({len(changed)} key(s)); backup: {bak.relative_to(ROOT)}")
    return 0


def cmd_generate(force: bool) -> int:
    if TOKENS_PATH.is_file() and not force:
        print("[manage-tokens] generate: tokens/tokens.yaml exists; "
              "use --force to overwrite (a backup is made)")
        return 1
    tokens = parse_tokens(EXAMPLE_PATH.read_text(encoding="utf-8"))
    n = 0
    for instance, agents in tokens.get("doors", {}).items():
        for agent in list(agents):
            agents[agent] = secrets.token_hex(24)  # 48 hex chars
            n += 1
    if TOKENS_PATH.is_file():
        bak = backup()
        print(f"[manage-tokens] backup: {bak.relative_to(ROOT)}")
    TOKENS_PATH.write_text(dump_tokens(tokens), encoding="utf-8")
    print(f"[manage-tokens] wrote {TOKENS_PATH.relative_to(ROOT)} "
          f"({n} fresh door secrets; fill llm/linear/github yourself or run migrate)")
    return 0


def _write_registry(path: Path, entries: dict) -> None:
    """Write a door registry, preserving non-secret fields already present.

    Only `secret` is authoritative from tokens.yaml; fields the instance
    added itself (e.g. `wake_hint`) are kept as-is.
    """
    existing = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
    merged = {}
    for agent, cfg in entries.items():
        prev = existing.get(agent) or {}
        if not isinstance(prev, dict):
            prev = {}
        merged[agent] = {**prev, **cfg}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def verify_canonical_client() -> list[str]:
    """Composition spec: instances SHALL NOT ship a divergent crew-send.py.

    The canonical client is crew/crew-send.py, delivered to containers by a
    read-only mount. Any per-instance copy that still exists must be
    byte-identical (SHA-256); a divergent copy is a spec violation. Returns a
    list of violation descriptions (empty = compliant).
    """
    import hashlib

    canonical = ROOT / "crew" / "crew-send.py"
    if not canonical.is_file():
        return ["crew/crew-send.py missing"]
    sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
    violations = []
    instances_dir = ROOT / "instances"
    if not instances_dir.is_dir():
        return violations
    for inst in sorted(instances_dir.iterdir()):
        copy = inst / "crew" / "crew-send.py"
        if not copy.is_file():
            continue
        if hashlib.sha256(copy.read_bytes()).hexdigest() != sha:
            violations.append(
                f"{copy.relative_to(ROOT)} diverges from canonical "
                "crew/crew-send.py (sha256 mismatch)")
    return violations


def cmd_derive_agents() -> int:
    """Regenerate every door registry (office + each instance) from tokens.yaml.

    Also verifies the canonical door client rule (no divergent per-instance
    crew-send.py copies) so the sync step enforces the composition spec.
    """
    violations = verify_canonical_client()
    if violations:
        for v in violations:
            print(f"[manage-tokens] SPEC VIOLATION: {v}")
        print("[manage-tokens] remove the copy; the canonical client is "
              "delivered by the read-only mount at /opt/crew/crew-send.py")
        return 1
    tokens = load_tokens()
    doors = tokens.get("doors") or {}
    written = 0

    # Office registry — host ports differ per agent.
    office = doors.get("office") or {}
    entries = {}
    for agent, port in OFFICE_PORTS.items():
        entries[agent] = {
            "host_url": f"http://127.0.0.1:{port}/webhooks/inbox",
            "container_url": f"http://{agent}:8644/webhooks/inbox",
            "secret": office.get(agent, ""),
        }
    _write_registry(AGENTS_PATH, entries)
    print(f"[manage-tokens] wrote {AGENTS_PATH.relative_to(ROOT)} "
          f"({len(entries)} office doors)")
    written += len(entries)

    # Instance registries — agents talk to each other through these, so a
    # rotation that skips them silently breaks intra-team messaging (401).
    for instance, agents in doors.items():
        if instance == "office":
            continue
        path = ROOT / "instances" / instance / "crew" / "agents.json"
        if not path.parent.is_dir():
            print(f"[manage-tokens] skip {instance}: no {path.parent.relative_to(ROOT)}")
            continue
        entries = {}
        for agent, secret in agents.items():
            entries[agent] = {
                "container_url":
                    f"http://{instance}-{agent}:8644/webhooks/inbox",
                "secret": secret,
            }
        _write_registry(path, entries)
        print(f"[manage-tokens] wrote {path.relative_to(ROOT)} "
              f"({len(entries)} {instance} doors)")
        written += len(entries)

    print(f"[manage-tokens] {written} door(s) synced from tokens.yaml")
    return 0


def cmd_rotate_doors() -> int:
    """Regenerate every door secret; keep llm/linear/github untouched."""
    tokens = load_tokens()
    if not tokens.get("doors"):
        print("[manage-tokens] rotate-doors: no doors section found")
        return 1
    n = 0
    for instance, agents in tokens["doors"].items():
        for agent in list(agents):
            agents[agent] = secrets.token_hex(24)
            n += 1
    bak = backup()
    TOKENS_PATH.write_text(dump_tokens(tokens), encoding="utf-8")
    print(f"[manage-tokens] rotated {n} door secret(s); "
          f"backup: {bak.relative_to(ROOT)}")
    print("[manage-tokens] update any external agent that signs requests with "
          "these doors, then run: python3 office/manage_tokens.py derive-agents")
    return 0


def cmd_set(path: str) -> int:
    """Set one dotted key from a hidden prompt (never echoed, never in history).

    Example:  python3 office/manage_tokens.py set llm.factories.office
    """
    import getpass

    if not path or "." not in path:
        print("[manage-tokens] set: need a dotted path, e.g. "
              "llm.factories.office / github.token / doors.office.architect",
              file=sys.stderr)
        return 2
    tokens = load_tokens()
    if not tokens:
        print(f"[manage-tokens] set: {TOKENS_PATH.relative_to(ROOT)} not found; "
              "run `generate` or `migrate` first", file=sys.stderr)
        return 2

    value = getpass.getpass(f"value for {path} (hidden, Enter to abort): ").strip()
    if not value:
        print("[manage-tokens] set: aborted (empty value)")
        return 1

    keys = path.split(".")
    node = tokens
    for k in keys[:-1]:
        nxt = node.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            node[k] = nxt
        node = nxt
    old = node.get(keys[-1]) or ""
    node[keys[-1]] = value

    bak = backup()
    TOKENS_PATH.write_text(dump_tokens(tokens), encoding="utf-8")
    print(f"[manage-tokens] set {path}: {mask(old)} -> {mask(value)}; "
          f"backup: {bak.relative_to(ROOT)}")
    print("[manage-tokens] remember to delete the backup once verified: "
          f"rm {bak.relative_to(ROOT)}")
    return 0


def _walk_scalars(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_scalars(v, f"{path}.{k}" if path else k)
    elif isinstance(node, str) and node:
        yield path, node


def load_revoked() -> dict:
    """{sha256: description} of credentials that must never be active again."""
    if not REVOKED_PATH.is_file():
        return {}
    out = {}
    for raw in REVOKED_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        out[parts[0].lower()] = parts[1] if len(parts) > 1 else "revoked"
    return out


def cmd_check() -> int:
    import hashlib

    tokens = load_tokens()
    missing = []
    for instance, agents in tokens.get("doors", {}).items():
        for agent, secret in agents.items():
            if not secret:
                missing.append(f"doors.{instance}.{agent}")
    for factory in ("office", "dev-crew", "lab-crew", "product-factory"):
        if not (tokens.get("llm", {}).get("factories", {}).get(factory)):
            missing.append(f"llm.factories.{factory}")
    for p in ("github.token", "linear.api_key"):
        node = tokens
        for k in p.split("."):
            node = node.get(k, {})
        if not node:
            missing.append(p)

    # Revoked / known-leaked values must never be active again.
    revoked = load_revoked()
    reused = []
    if revoked:
        for path, value in _walk_scalars(tokens):
            digest = hashlib.sha256(value.encode()).hexdigest()
            if digest in revoked:
                reused.append(f"{path} == {revoked[digest]}")

    if reused:
        print(f"[manage-tokens] check: {len(reused)} REVOKED credential(s) still "
              f"in use — rotate now:", file=sys.stderr)
        for r in reused:
            print(f"  ! {r}", file=sys.stderr)
    if missing:
        print(f"[manage-tokens] check: {len(missing)} missing:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
    if reused or missing:
        return 1
    print("[manage-tokens] check: OK (complete, no revoked credentials in use)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "check"
    if cmd == "migrate":
        return cmd_migrate("--dry-run" in args)
    if cmd == "generate":
        return cmd_generate("--force" in args)
    if cmd == "rotate-doors":
        return cmd_rotate_doors()
    if cmd == "set":
        return cmd_set(args[1] if len(args) > 1 else "")
    if cmd == "derive-agents":
        return cmd_derive_agents()
    if cmd == "check":
        return cmd_check()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

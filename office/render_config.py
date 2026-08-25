#!/usr/bin/env python3
"""Container entrypoint: resolve credentials -> render config + .env -> exec gateway.

One implementation serves both Office agents and team agents:

  1. load  $TOKENS_FILE  (default /opt/tokens/tokens.yaml)
  2. resolve this agent's credentials via FACTORY_NAME / TEAM_NAME / AGENT_ID
  3. substitute ${VAR} placeholders in /opt/data/config.yaml.template
  4. write the resolved secrets into /opt/data/.env  (see below)
  5. exec ``hermes gateway run``

Why step 4: ``hermes gateway run`` hands off to s6 supervision, and the
supervised gateway is started from the *container* environment — not from this
process's environment. Anything we only put in os.environ (GITHUB_TOKEN,
LINEAR_API_KEY, ...) is therefore invisible to the agent and to the shell
commands its skills run. Hermes loads ``$HERMES_HOME/.env`` with
``override=True``, so that file is the supported channel for per-agent
credentials. It is gitignored (``agents/*/hermes-home/.env``) and written 0600.

Keys this script does not manage (e.g. API_SERVER_KEY, seeded on first boot)
are preserved.

Fails fast (exit 2) if the tokens file or a referenced placeholder is missing,
instead of booting a gateway with a literal ``${DOOR_SECRET}``.

Test without booting the gateway:
    AGENT_ID=architect FACTORY_NAME=office \
      python3 office/render_config.py --render-only
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from credentials import CredentialsError, load_tokens, resolve_identity  # noqa: E402

TEMPLATE = "/opt/data/config.yaml.template"
TARGET = "/opt/data/config.yaml"
ENV_FILE = "/opt/data/.env"
GATEWAY_ARGV = ["hermes", "gateway", "run"]

# Credentials the agent needs as environment variables (tools/skills read them).
ENV_KEYS = ("GITHUB_TOKEN", "LINEAR_API_KEY", "CUSTOM_API_KEY",
            "OPENROUTER_API_KEY", "LLM_BASE_URL")

_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def render(template: str, target: str) -> int:
    try:
        text = open(template, encoding="utf-8").read()
    except OSError as exc:
        raise CredentialsError(f"cannot read template {template}: {exc}") from exc

    def sub(m: "re.Match") -> str:
        var = m.group(1)
        if var not in os.environ:
            raise CredentialsError(
                f"config.yaml.template references ${{{var}}} but it is not set")
        return os.environ[var]

    rendered = _VAR.sub(sub, text)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(rendered)
    return len(rendered)


def write_env_file(path: str, resolved: dict) -> list[str]:
    """Merge the resolved credentials into $HERMES_HOME/.env (0600).

    Existing keys we do not manage are kept as-is, so first-boot secrets such
    as API_SERVER_KEY survive a restart.
    """
    existing: dict[str, str] = {}
    order: list[str] = []
    if os.path.isfile(path):
        try:
            for raw in open(path, encoding="utf-8"):
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                if k not in existing:
                    order.append(k)
                existing[k] = v
        except OSError:
            pass

    written = []
    for key in ENV_KEYS:
        val = resolved.get(key)
        if not val:
            continue
        if key not in existing:
            order.append(key)
        existing[key] = val
        written.append(key)

    body = ["# Managed by office/render_config.py — do not edit by hand.",
            "# Secrets come from the single source of truth: tokens/tokens.yaml.",
            ""]
    body += [f"{k}={existing[k]}" for k in order if k in existing]

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body) + "\n")
    os.chmod(path, 0o600)
    return written


def main() -> int:
    render_only = "--render-only" in sys.argv
    tokens_file = os.environ.get("TOKENS_FILE", "/opt/tokens/tokens.yaml")
    factory = os.environ.get("FACTORY_NAME", "office")
    team = os.environ.get("TEAM_NAME", "")
    agent = os.environ.get("AGENT_ID", "")

    if not agent:
        print("[render-config] FATAL: AGENT_ID not set", file=sys.stderr)
        return 2

    try:
        tokens = load_tokens(tokens_file)
        resolved = resolve_identity(
            tokens, factory=factory, team=team, agent=agent)
        os.environ.update(resolved)
        n = render(TEMPLATE, TARGET)
        env_keys = write_env_file(ENV_FILE, resolved)
    except CredentialsError as exc:
        print(f"[render-config] FATAL: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[render-config] FATAL: cannot write {ENV_FILE}: {exc}",
              file=sys.stderr)
        return 2

    print(f"[render-config] wrote {TARGET} ({n} bytes) "
          f"factory={factory} team={team or 'office'} agent={agent}", flush=True)
    print(f"[render-config] wrote {ENV_FILE} (0600) with "
          f"{len(env_keys)} credential(s): {', '.join(env_keys) or 'none'}",
          flush=True)

    if render_only:
        return 0

    os.execvpe("hermes", GATEWAY_ARGV, os.environ)  # no return


if __name__ == "__main__":
    sys.exit(main())

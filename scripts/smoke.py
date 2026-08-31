#!/usr/bin/env python3
"""Agent Office — foundation smoke test.

Hierarchical checks that the Office shell foundation still works after local
changes. Fast, no LLM wait. Exit 0 = foundation ok.

Levels (higher includes lower):
  0  static   — paths, action-schema JSON, agents registry
  1  infra    — Redis PING, key containers present
  2  bus      — publish + readback on office:events
  3  doors    — optional wake + signed door POST → 2xx

Usage:
  python3 scripts/smoke.py
  python3 scripts/smoke.py --level 2
  python3 scripts/smoke.py --agents scrum-master --no-wake
  python3 scripts/smoke.py --json

Env:
  OFFICE_BUS_URL  default redis://127.0.0.1:6380
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STREAM = "office:events"
INBOX_PREFIX = "office:inbox:"

OFFICE_AGENTS = [
    "architect",
    "staff-engineer",
    "scrum-master",
    "super-devops",
]

CONTAINER_BY_AGENT = {
    "architect": "agent-office-architect",
    "staff-engineer": "agent-office-staff-engineer",
    "scrum-master": "agent-office-scrum-master",
    "super-devops": "agent-office-super-devops",
}

ALWAYS_ON = [
    "agent-office-shared-memory",
    "agent-office-factory-control",
]

REQUIRED_PATHS = [
    "docker-compose.yml",
    "bus/action-schema.json",
    "crew/publish-event.py",
    "crew/crew-send.py",
    "crew/office-log.py",
    "crew/agents.example.json",
    "office/bus/client.py",
    "office/lifecycle/factory_control.py",
]


# ---- tiny Redis (same RESP subset as crew/publish-event.py) -----------------

def parse_bus_url(url: str) -> tuple[str, int, int]:
    u = urlparse(url)
    host = u.hostname or "127.0.0.1"
    port = u.port or 6379
    db = 0
    if u.path and len(u.path) > 1 and u.path[1:].isdigit():
        db = int(u.path[1:])
    return host, port, db


class RedisLite:
    def __init__(self, host: str, port: int, db: int = 0, timeout: float = 5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.file = self.sock.makefile("rb")
        if db:
            self._call("SELECT", str(db))

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def _encode(self, *parts: str) -> bytes:
        out = [f"*{len(parts)}\r\n".encode()]
        for p in parts:
            b = p.encode("utf-8")
            out.append(f"${len(b)}\r\n".encode())
            out.append(b)
            out.append(b"\r\n")
        return b"".join(out)

    def _read(self):
        line = self.file.readline()
        if not line:
            raise ConnectionError("Redis connection closed")
        t, payload = line[:1], line[1:-2]
        if t == b"+":
            return payload.decode()
        if t == b"-":
            raise RuntimeError(payload.decode())
        if t == b":":
            return int(payload)
        if t == b"$":
            n = int(payload)
            if n == -1:
                return None
            data = self.file.read(n + 2)
            return data[:-2].decode("utf-8", errors="replace")
        if t == b"*":
            n = int(payload)
            if n == -1:
                return None
            return [self._read() for _ in range(n)]
        raise RuntimeError(f"bad RESP: {line!r}")

    def _call(self, *parts: str):
        self.sock.sendall(self._encode(*parts))
        return self._read()

    def ping(self) -> bool:
        try:
            return self._call("PING") == "PONG"
        except Exception:
            return False

    def xadd(self, key: str, fields: dict) -> str:
        args = ["XADD", key, "*"]
        for k, v in fields.items():
            if v is not None and v != "":
                args.extend([k, str(v)])
        return self._call(*args)

    def xrevrange(self, key: str, count: int):
        return self._call("XREVRANGE", key, "+", "-", "COUNT", str(count)) or []

    def publish(self, channel: str, payload: str) -> int:
        return int(self._call("PUBLISH", channel, payload))


# ---- helpers ----------------------------------------------------------------

class SmokeError(Exception):
    pass


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}", flush=True)


def fail(msg: str) -> None:
    raise SmokeError(msg)


def sh(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def docker_names() -> set[str]:
    rc, out, _ = sh(["docker", "ps", "-a", "--format", "{{.Names}}"])
    if rc != 0:
        return set()
    return {n.strip() for n in out.splitlines() if n.strip()}


def docker_running(name: str) -> bool:
    rc, out, _ = sh(
        ["docker", "inspect", "-f", "{{.State.Running}}", name], timeout=10
    )
    return rc == 0 and out.strip() == "true"


def pairs_to_dict(flat: list) -> dict:
    d: dict = {}
    for i in range(0, len(flat or []), 2):
        if i + 1 < len(flat):
            d[flat[i]] = flat[i + 1]
    return d


def load_agents_registry() -> dict:
    path = ROOT / "crew" / "agents.json"
    if not path.is_file():
        fail(
            f"missing {path.relative_to(ROOT)}. "
            "Copy crew/agents.example.json → crew/agents.json and set secrets."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not data:
        fail("crew/agents.json is empty or invalid")
    return data


def sign(secret: str, payload: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def door_post(url: str, secret: str, message: str, timeout: float = 15.0,
              attempts: int = 6, backoff: float = 3.0) -> int:
    """POST a signed message to an agent door, retrying transient boot races.

    A freshly woken container reports Running before its gateway binds the
    port, so the first POST can hit a closed/half-open socket
    ("connection reset by peer"). HTTP responses — including 401 — are
    returned immediately; only connection-level failures are retried.
    """
    body = json.dumps({"message": message}, ensure_ascii=False)
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sign(secret, body),
    }
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            url, data=body.encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status
        except urllib.error.HTTPError:
            raise                      # real HTTP answer — do not retry
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(backoff)
    raise last if last else RuntimeError("door_post failed")


# ---- levels -----------------------------------------------------------------

def level0_static() -> None:
    log("level 0 — static")
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    if missing:
        fail(f"missing required paths: {', '.join(missing)}")
    ok(f"required paths present ({len(REQUIRED_PATHS)})")

    schema = ROOT / "bus" / "action-schema.json"
    try:
        data = json.loads(schema.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"action-schema.json not valid JSON: {e}")
    if not isinstance(data, dict) or "properties" not in data:
        fail("action-schema.json does not look like the Office envelope schema")
    ok("bus/action-schema.json valid")

    example = ROOT / "crew" / "agents.example.json"
    if not example.is_file():
        fail("crew/agents.example.json missing")
    agents_path = ROOT / "crew" / "agents.json"
    if agents_path.is_file():
        ok("crew/agents.json present")
    else:
        ok("crew/agents.json absent (doors level will fail until copied from example)")

    # Canonical client rule (composition spec): instances SHALL NOT ship their
    # own crew-send.py copy — the client arrives by the read-only mount. Any
    # leftover copy must be byte-identical (SHA-256) to the canonical file.
    canonical_path = ROOT / "crew" / "crew-send.py"
    canonical_sha = hashlib.sha256(
        canonical_path.read_bytes()).hexdigest()
    copies = sorted((ROOT / "instances").glob("*/crew/crew-send.py"))
    divergent = [
        p for p in copies
        if hashlib.sha256(p.read_bytes()).hexdigest() != canonical_sha
    ]
    if divergent:
        fail(
            "per-instance crew-send.py diverges from the canonical client "
            f"(remove the copy or re-sync): {', '.join(str(p.relative_to(ROOT)) for p in divergent)}"
        )
    if copies:
        log(
            "warning: per-instance crew-send.py copies still present "
            "(byte-identical, but the canonical mount is the contract): "
            + ", ".join(str(p.relative_to(ROOT)) for p in copies)
        )
    ok(f"canonical client rule: no divergent copies ({len(copies)} found, SHA-256 checked)")


def level1_infra(bus_url: str) -> RedisLite:
    log("level 1 — infra")
    host, port, db = parse_bus_url(bus_url)
    try:
        r = RedisLite(host, port, db)
    except OSError as e:
        fail(f"Redis unreachable at {host}:{port}: {e}")
    if not r.ping():
        r.close()
        fail(f"Redis PING failed at {host}:{port}")
    ok(f"Redis PING ok ({host}:{port})")

    names = docker_names()
    if not names:
        # docker may be unavailable in some environments; soft-warn but still
        # require Redis which is the hard dependency for higher levels.
        log("warning: docker not reachable or no containers — container checks skipped")
        return r

    for c in ALWAYS_ON:
        if c not in names:
            fail(f"expected always-on container missing: {c}")
        ok(f"container known: {c}")

    for agent, cname in CONTAINER_BY_AGENT.items():
        if cname not in names:
            fail(f"expected Office agent container missing: {cname} ({agent})")
        state = "running" if docker_running(cname) else "stopped"
        ok(f"container known: {cname} ({state})")

    return r


def level2_bus(r: RedisLite, run_id: str) -> None:
    log("level 2 — bus")
    summary = f"foundation smoke start {run_id}"
    fields = {
        "action": "agent.online",
        "actor": "smoke",
        "summary": summary,
        "target": "*",
        "timestamp": ts(),
        "project": "",
        "team": "",
    }
    try:
        eid = r.xadd(STREAM, fields)
    except Exception as e:
        fail(f"XADD office:events failed: {e}")
    ok(f"published {eid} agent.online by smoke")

    rows = r.xrevrange(STREAM, 20)
    found = False
    for row in rows:
        if not row or len(row) < 2:
            continue
        fields_d = pairs_to_dict(row[1])
        if fields_d.get("summary") == summary and fields_d.get("actor") == "smoke":
            found = True
            break
    if not found:
        fail("published smoke event not found in XREVRANGE office:events")
    ok("bus readback ok")


def request_wake(r: RedisLite, agent_id: str) -> None:
    """Publish agent.wake to durable stream + agent inbox (factory-control path)."""
    env = {
        "id": str(uuid.uuid4()),
        "actor": "smoke",
        "action": "agent.wake",
        "target": agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "payload": {"summary": f"smoke wake {agent_id}", "reason": "foundation-smoke"},
    }
    payload_json = json.dumps(env, ensure_ascii=False)
    r.xadd(
        STREAM,
        {
            "action": "agent.wake",
            "actor": "smoke",
            "target": agent_id,
            "timestamp": env["timestamp"],
            "summary": f"smoke wake {agent_id}",
            "json": payload_json,
        },
    )
    r.publish(INBOX_PREFIX + agent_id, payload_json)


def wait_running(cname: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if docker_running(cname):
            return True
        time.sleep(2)
    return False


def level3_doors(
    r: RedisLite,
    agents: list[str],
    no_wake: bool,
    wake_timeout: int,
    run_id: str,
) -> None:
    log("level 3 — doors + lifecycle")
    registry = load_agents_registry()

    for agent in agents:
        if agent not in registry:
            fail(f"agent '{agent}' not in crew/agents.json")
        if agent not in CONTAINER_BY_AGENT:
            fail(f"unknown Office agent for smoke: {agent}")

        cname = CONTAINER_BY_AGENT[agent]
        cfg = registry[agent]
        host_url = cfg.get("host_url")
        secret = cfg.get("secret")
        if not host_url or not secret:
            fail(f"{agent}: host_url/secret missing in agents.json")

        running = docker_running(cname)
        if not running:
            if no_wake:
                fail(f"{agent}: container {cname} stopped and --no-wake set")
            log(f"  waking {agent} ({cname})…")
            request_wake(r, agent)
            if not wait_running(cname, wake_timeout):
                fail(
                    f"{agent}: wake timeout after {wake_timeout}s "
                    f"(container {cname} still not Running)"
                )
            # brief grace for Hermes gateway bind
            time.sleep(3)
            ok(f"{agent}: container Running after wake")
        else:
            ok(f"{agent}: container already Running")

        msg = f"smoke: ping from foundation check ({run_id})"
        try:
            status = door_post(host_url, secret, msg)
        except urllib.error.HTTPError as e:
            fail(f"{agent}: door HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
        except Exception as e:
            fail(f"{agent}: door error: {e}")

        if status < 200 or status >= 300:
            fail(f"{agent}: door returned {status}, expected 2xx")
        ok(f"{agent}: door accepted ({status})")

    # completion event
    r.xadd(
        STREAM,
        {
            "action": "agent.online",
            "actor": "smoke",
            "summary": f"foundation smoke ok {run_id}",
            "target": "*",
            "timestamp": ts(),
        },
    )
    ok("published completion event")


# ---- main -------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Agent Office foundation smoke test")
    ap.add_argument("--level", type=int, default=3, choices=[0, 1, 2, 3])
    ap.add_argument(
        "--agents",
        default=",".join(OFFICE_AGENTS),
        help="comma-separated Office agent ids for door checks",
    )
    ap.add_argument("--no-wake", action="store_true")
    ap.add_argument(
        "--url",
        default=os.environ.get("OFFICE_BUS_URL", "redis://127.0.0.1:6380"),
    )
    ap.add_argument(
        "--wake-timeout",
        type=int,
        default=int(os.environ.get("WAKE_TIMEOUT_S", "90")),
    )
    ap.add_argument("--json", action="store_true", help="print machine summary")
    args = ap.parse_args()

    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    run_id = uuid.uuid4().hex[:8]
    result: dict[str, Any] = {
        "run_id": run_id,
        "level": args.level,
        "ok": False,
        "error": None,
    }

    r: RedisLite | None = None
    try:
        log(f"foundation smoke start id={run_id} level={args.level}")
        level0_static()
        if args.level >= 1:
            r = level1_infra(args.url)
        if args.level >= 2:
            if r is None:
                host, port, db = parse_bus_url(args.url)
                r = RedisLite(host, port, db)
            level2_bus(r, run_id)
        if args.level >= 3:
            if r is None:
                host, port, db = parse_bus_url(args.url)
                r = RedisLite(host, port, db)
            level3_doors(r, agents, args.no_wake, args.wake_timeout, run_id)

        result["ok"] = True
        log("PASS — foundation ok")
        if args.json:
            print(json.dumps(result))
        return 0
    except SmokeError as e:
        result["error"] = str(e)
        print(f"[smoke] FAIL: {e}", file=sys.stderr)
        if args.json:
            print(json.dumps(result))
        return 1
    except Exception as e:
        result["error"] = f"unexpected: {e}"
        print(f"[smoke] FAIL unexpected: {e}", file=sys.stderr)
        if args.json:
            print(json.dumps(result))
        return 2
    finally:
        if r is not None:
            r.close()


if __name__ == "__main__":
    sys.exit(main())

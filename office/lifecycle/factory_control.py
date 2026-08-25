#!/usr/bin/env python3
"""Agent Office — factory-control lifecycle supervisor.

Runs inside the always-on `factory-control` container. The ONLY component
permitted to start/stop registered agent containers (registry allowlist in
office/registry/factory-agents.json).

Loops:
  1. Idle reaper (every CHECK_INTERVAL): stop registered agents whose last
     task-work log line is older than IDLE_TIMEOUT. Fail-open when the
     signal is unreadable; busy-locked agents are never stopped.
  2. Wake listener: office:inbox:* envelopes with action=agent.wake start
     the target container (idempotent), wait for health, emit events.

Events go through the durable publish path (bus.client.publish_event).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("FACTORY_REPO", "/opt/repo"))
REGISTRY = Path(os.environ.get(
    "FACTORY_REGISTRY", str(REPO / "office/registry/factory-agents.json")))
IDLE_TIMEOUT_S = int(os.environ.get("IDLE_TIMEOUT_S", str(40 * 60)))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "120"))
WAKE_TIMEOUT_S = int(os.environ.get("WAKE_TIMEOUT_S", "90"))
BUSY_LOCK_TTL_S = int(os.environ.get("BUSY_LOCK_TTL_S", str(15 * 60)))
DOOR_PORTS = {}                                    # id -> host port (optional)

sys.path.insert(0, "/opt/office-lib")
from bus.client import BusClient, make_envelope, publish_event  # noqa: E402

ACTIVITY_MARKS = ("conversation_loop:", "tool_executor:", "inbound message",
                  "response ready:")


def sh(cmd: list[str], timeout: int | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout


def log(msg: str) -> None:
    print(f"[fc] {datetime.now(timezone.utc):%H:%M:%S} {msg}", flush=True)


def emit(action: str, target: str, summary: str) -> None:
    try:
        publish_event(BusClient(), make_envelope(
            actor="factory-control", action=action, target=target,
            payload={"summary": summary}))
        log(f"emit {action} {target}: {summary}")
    except Exception as exc:
        log(f"bus publish failed ({action} {target}): {exc}")


def load_registry() -> list[dict]:
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    agents = raw.get("agents") or []
    assert isinstance(agents, list) and agents, f"empty registry: {REGISTRY}"
    return agents


# ---- activity signal ------------------------------------------------------

def _parse_log_ts(line: str) -> datetime | None:
    try:
        return datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f") \
            .replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def seconds_idle(log_path: Path) -> float | None:
    """Seconds since last task-work log line; mtime fallback after rotation;
    None when no readable signal (fail-open)."""
    if not log_path.exists():
        return None
    try:
        with open(log_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    newest = None
    for line in tail.splitlines():
        if any(m in line for m in ACTIVITY_MARKS):
            ts = _parse_log_ts(line)
            if ts and (newest is None or ts > newest):
                newest = ts
    if newest is not None:
        return max(0.0, (datetime.now(timezone.utc) - newest).total_seconds())
    # rotation fallback: no task-work line at all -> trust file mtime
    try:
        mtime = datetime.fromtimestamp(log_path.stat().st_mtime,
                                       tz=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - mtime).total_seconds())
    except OSError:
        return None


def busy(agent_id: str, bus: BusClient) -> bool:
    try:
        return bool(bus.get_key(f"office:busy:{agent_id}"))
    except Exception:
        return False


# ---- docker ---------------------------------------------------------------

def running_containers() -> set[str]:
    rc, out = sh(["docker", "ps", "--format", "{{.Names}}"])
    return set(out.split()) if rc == 0 else set()


def docker_start(name: str) -> tuple[bool, str]:
    rc, out = sh(["docker", "start", name])
    if rc != 0:
        return False, out.strip()[:200]
    deadline = time.time() + WAKE_TIMEOUT_S
    while time.time() < deadline:
        rrc, rout = sh(["docker", "ps", "--format",
                        "{{.Names}}|{{.Status}}"])
        for line in rout.splitlines():
            n, _, st = line.partition("|")
            if n == name and "healthy" in st.lower():
                return True, st
        time.sleep(3)
    # health label may be absent; accept "running" past timeout
    rrc, rout = sh(["docker", "inspect", "-f",
                    "{{.State.Running}}|{{.State.Health.Status}}", name])
    if rout.startswith("true"):
        return True, rout.strip()
    return False, f"health wait timeout after {WAKE_TIMEOUT_S}s"


def healthy_via_door(name: str) -> bool:
    port = DOOR_PORTS.get(name)
    if not port:
        return True                      # no door mapping -> skip probe
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/webhooks/inbox", method="POST",
            data=b"{}", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return True                      # 4xx/5xx still means gateway is up


# ---- reaper ---------------------------------------------------------------

def reap_once(registry: list[dict]) -> None:
    bus = BusClient()
    running = running_containers()
    now = time.time()
    for a in registry:
        name = a["container"]
        if name not in running:
            continue
        if busy(a["id"], bus):
            continue
        idle = seconds_idle(REPO / a["log_path"] / "logs/agent.log")
        if idle is None or idle < IDLE_TIMEOUT_S:
            continue
        log(f"stopping {name}: idle {int(idle // 60)}m >= "
            f"{IDLE_TIMEOUT_S // 60}m")
        rc, _ = sh(["docker", "stop", "-t", "30", name], timeout=60)
        emit("agent.stopped", a["id"],
             f"idle {int(idle // 60)}m >= {IDLE_TIMEOUT_S // 60}m"
             + ("" if rc == 0 else " (stop command failed)"))


# ---- wake -----------------------------------------------------------------

def wake(target: str, registry: list[dict]) -> None:
    entry = next((a for a in registry
                  if a["id"] == target or a["container"] == target), None)
    if entry is None:
        log(f"wake ignored: '{target}' not in registry")
        return
    name = entry["container"]
    if name in running_containers():
        return                                        # idempotent no-op
    log(f"waking {name}")
    ok, note = docker_start(name)
    if ok:
        healthy_via_door(name)
        emit("agent.started", entry["id"], "wake")
    else:
        emit("agent.wake_failed", entry["id"], note)


def listen_wakes(registry: list[dict]) -> None:
    """PSUBSCRIBE office:inbox:*; reconnect quietly on socket timeouts.

    Known trade-off (spec'd): envelopes published while we are down are lost.
    """
    while True:
        try:
            bus = BusClient()
            for _ch, msg in bus.psubscribe(["office:inbox:*"]):
                try:
                    env = json.loads(msg)
                    if env.get("action") == "agent.wake":
                        wake(env.get("target") or "", registry)
                except Exception as exc:
                    log(f"bad inbox msg: {exc}")
        except Exception:
            time.sleep(2)


def main() -> int:
    registry = load_registry()
    log(f"online: agents={len(registry)} idle={IDLE_TIMEOUT_S}s "
        f"interval={CHECK_INTERVAL}s wake={WAKE_TIMEOUT_S}s")
    threading.Thread(target=listen_wakes, args=(registry,), daemon=True).start()
    while True:
        try:
            reap_once(registry)
        except Exception as exc:
            log(f"reap error: {exc}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())

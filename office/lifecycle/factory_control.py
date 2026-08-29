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
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("FACTORY_REPO", "/opt/repo"))
REGISTRY = Path(os.environ.get(
    "FACTORY_REGISTRY", str(REPO / "office/registry/factory-agents.json")))
IDLE_TIMEOUT_S = int(os.environ.get("IDLE_TIMEOUT_S", str(40 * 60)))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "120"))
WAKE_TIMEOUT_S = int(os.environ.get("WAKE_TIMEOUT_S", "90"))
DOOR_PORT = int(os.environ.get("DOOR_PORT", "8644"))

sys.path.insert(0, "/opt/office-lib")
from bus.client import BusClient, make_envelope, publish_event  # noqa: E402

ACTIVITY_MARKS = ("conversation_loop:", "tool_executor:", "inbound message",
                  "response ready:")


def sh(cmd: list[str], timeout: int | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout


def log(msg: str) -> None:
    print(f"[fc] {datetime.now(timezone.utc):%H:%M:%S} {msg}", flush=True)


def emit(action: str, target: str, summary: str,
         extra: dict | None = None) -> None:
    try:
        payload = {"summary": summary}
        if extra:
            payload.update(extra)
        publish_event(BusClient(), make_envelope(
            actor="factory-control", action=action, target=target,
            payload=payload))
        log(f"emit {action} {target}: {summary}")
    except Exception as exc:
        log(f"bus publish failed ({action} {target}): {exc}")


def load_registry() -> list[dict]:
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    agents = raw.get("agents") or []
    if not isinstance(agents, list) or not agents:
        raise ValueError(f"empty or invalid registry: {REGISTRY}")
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


def container_started_at(name: str) -> datetime | None:
    """Container start time (UTC) from docker inspect; None on failure."""
    rc, out = sh(["docker", "inspect", "-f", "{{.State.StartedAt}}", name])
    if rc != 0 or not out.strip():
        return None
    try:
        return datetime.fromisoformat(out.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def effective_idle(idle_from_log: float | None,
                   started_at: datetime | None,
                   now: datetime) -> float | None:
    """Idle bounded by time since container start (2b).

    A just-started agent whose log still holds the previous session's
    task-work lines must not be reaped for stale idleness — a process that
    started T seconds ago can never have been idle longer than T seconds.
    """
    if started_at is None:
        return idle_from_log
    since_start = max(0.0, (now - started_at).total_seconds())
    if idle_from_log is None:
        return since_start
    return min(idle_from_log, since_start)


def busy(agent_id: str, bus: BusClient) -> bool | None:
    """True/False from bus; None on error (fail-safe: skip the agent)."""
    try:
        return bool(bus.get_key(f"office:busy:{agent_id}"))
    except Exception:
        return None


# ---- docker ---------------------------------------------------------------

def running_containers() -> set[str]:
    rc, out = sh(["docker", "ps", "--format", "{{.Names}}"])
    return set(out.split()) if rc == 0 else set()


def door_open(name: str, port: int = DOOR_PORT, timeout: float = 2.0) -> bool:
    """True when the agent's gateway accepts a TCP connection on its door.

    factory-control shares the `crew` network with the agents, so the
    container name resolves via Docker DNS. This is the readiness signal —
    State.Running alone fires before the gateway binds the port.
    """
    try:
        with socket.create_connection((name, port), timeout=timeout):
            return True
    except OSError:
        return False


def docker_start(name: str) -> tuple[bool, str]:
    """Start and wait for the container to be Running (poll every 2s).

    Agent containers define no docker healthcheck, so "healthy" in the
    docker sense never appears. Readiness = the gateway actually accepts a
    TCP connection on its door port (spec: health = door responds / gateway
    ready). Waiting only for State.Running returns too early: the container
    is up but the gateway has not bound the port yet, so callers that send
    immediately after a wake get "connection reset by peer".
    """
    rc, out = sh(["docker", "start", name])
    if rc != 0:
        return False, out.strip()[:200]
    deadline = time.time() + WAKE_TIMEOUT_S
    running_seen = False
    while time.time() < deadline:
        if not running_seen:
            # Guard .State.Health: agent containers declare no healthcheck, and
            # `{{.State.Health.Status}}` makes `docker inspect` fail outright
            # with "map has no entry for key Health" (exit 1, empty output) —
            # which used to make every wake time out as wake_failed.
            rrc, rout = sh([
                "docker", "inspect", "-f",
                "{{.State.Running}}|"
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                name])
            running, _, health = rout.strip().partition("|")
            running_seen = (rrc == 0 and running == "true"
                            and health in ("", "none", "healthy"))
        if running_seen and door_open(name):
            return True, "door ready"
        time.sleep(2)
    if running_seen:
        return False, (f"gateway did not open port {DOOR_PORT} within "
                       f"{WAKE_TIMEOUT_S}s (container is running)")
    return False, f"start wait timeout after {WAKE_TIMEOUT_S}s"


# ---- reaper ---------------------------------------------------------------

def reap_once(registry: list[dict], bus: BusClient) -> None:
    running = running_containers()
    for a in registry:
        name = a["container"]
        if name not in running:
            continue
        is_busy = busy(a["id"], bus)
        if is_busy is None:
            log(f"skip {name}: bus unavailable (fail-safe)")
            continue
        if is_busy:
            continue
        idle = effective_idle(
            seconds_idle(REPO / a["log_path"] / "logs/agent.log"),
            container_started_at(name),
            datetime.now(timezone.utc))
        if idle is None or idle < IDLE_TIMEOUT_S:
            continue
        log(f"stopping {name}: idle {int(idle // 60)}m >= "
            f"{IDLE_TIMEOUT_S // 60}m")
        rc, _ = sh(["docker", "stop", "-t", "30", name], timeout=60)
        emit("agent.stopped", a["id"],
             f"idle {int(idle // 60)}m >= {IDLE_TIMEOUT_S // 60}m"
             + ("" if rc == 0 else " (stop command failed)"),
             extra={"idle_seconds": int(idle)})


# ---- wake -----------------------------------------------------------------

def normalize_target(target: str) -> str:
    """Map colon-form 'team:role' (the wake_hint shipped in per-instance
    door registries) to the canonical registry-id form 'team-role'. The
    factory registry keys instance agents by hyphenated id."""
    return target.replace(":", "-")


def wake(target: str, registry: list[dict]) -> None:
    raw = target
    target = normalize_target(target)
    entry = next((a for a in registry
                  if a["id"] == target or a["container"] == target), None)
    if entry is None:
        emit("agent.wake_ignored", raw,
             f"wake target '{raw}' matched no registry entry",
             extra={"target": raw})
        return
    name = entry["container"]
    if name in running_containers():
        return                                        # idempotent no-op
    log(f"waking {name}")
    ok, note = docker_start(name)
    if ok:
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
    bus = BusClient()
    log(f"online: agents={len(registry)} idle={IDLE_TIMEOUT_S}s "
        f"interval={CHECK_INTERVAL}s wake={WAKE_TIMEOUT_S}s")
    threading.Thread(target=listen_wakes, args=(registry,), daemon=True).start()
    while True:
        try:
            reap_once(registry, bus)
        except Exception as exc:
            log(f"reap error: {exc}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())

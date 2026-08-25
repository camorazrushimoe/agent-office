#!/usr/bin/env python3
"""Agent Office idle reaper + wake listener (host-side supervisor).

Fixes the missing runtime half of docs/agent-lifecycle.md:
  - stops agent containers after IDLE_TIMEOUT without meaningful activity
    (activity = fresh task-work lines in the agent's logs/agent.log,
     same heuristic as factory-dashboard);
  - listens on the office bus for `agent.wake` and starts containers;
  - never touches always-on services (redis).

Run out-of-band (no container):  python3 idle_reaper.py [--dry-run]
Env: IDLE_TIMEOUT (default 50m), CHECK_INTERVAL (default 120s).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/ronnybonny/agent-office")
sys.path.insert(0, str(REPO / "office"))          # office-lib on sys.path

IDLE_TIMEOUT_S = int(os.environ.get("IDLE_TIMEOUT_S", str(40 * 60)))  # spec: 40m
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "120"))
ALWAYS_ON = {"agent-office-shared-memory"}

# container_name -> hermes_home relpath (for activity detection)
AGENTS = {
    "agent-office-architect": "agents/architect/hermes-home",
    "agent-office-staff-engineer": "agents/staff-engineer/hermes-home",
    "agent-office-scrum-master": "agents/scrum-master/hermes-home",
    "agent-office-super-devops": "agents/super-devops/hermes-home",
    "lab-1-research-lead": "instances/lab-1/home/research-lead",
    "lab-1-research-engineer": "instances/lab-1/home/research-engineer",
    "lab-1-evaluation": "instances/lab-1/home/evaluation",
    "spec-1-technical-product-manager": "instances/spec-1/home/technical-product-manager",
    "spec-1-product-researcher": "instances/spec-1/home/product-researcher",
    "spec-1-system-domain-analyst": "instances/spec-1/home/system-domain-analyst",
    "spec-1-adversarial-reviewer": "instances/spec-1/home/adversarial-reviewer",
    "dev-1-developer": "instances/dev-1/home/developer",
    "dev-1-tech-pm": "instances/dev-1/home/tech-pm",
    "dev-1-qa": "instances/dev-1/home/qa",
    "dev-1-devops": "instances/dev-1/home/devops",
}

ACTIVITY_MARKS = ("conversation_loop:", "tool_executor:", "inbound message",
                  "response ready:")


def parse_dur(s: str) -> int:
    s = s.strip().lower()
    return int(s[:-1]) * {"s": 1, "m": 60, "h": 3600}[s[-1]]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def running_containers() -> set[str]:
    return {l for l in sh(["docker", "ps", "--format", "{{.Names}}"]).split()}


def seconds_idle(home_rel: str) -> float | None:
    """Seconds since last meaningful task-work log line; None = unknown."""
    log = REPO / home_rel / "logs" / "agent.log"
    if not log.exists():
        return None
    try:
        with open(log, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    newest = None
    for line in tail.splitlines():
        if any(m in line for m in ACTIVITY_MARKS):
            try:
                ts = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f") \
                    .replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if newest is None or ts > newest:
                newest = ts
    if newest is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - newest).total_seconds())


def emit(action: str, target: str, summary: str) -> None:
    try:
        from bus.client import BusClient, make_envelope, publish_event
        bus = BusClient()
        publish_event(bus, make_envelope(
            actor="lifecycle", action=action, target=target,
            payload={"summary": summary}))
    except Exception as exc:                       # bus down — still reap
        print(f"[reaper] bus publish failed: {exc}", flush=True)


def stop_container(name: str, idle_min: int) -> None:
    print(f"[reaper] stopping {name}: idle {idle_min}m", flush=True)
    sh(["docker", "stop", "-t", "30", name])
    emit("agent.stopped", name.replace("agent-office-", "", 1),
         f"idle {idle_min}m >= {IDLE_TIMEOUT_S // 60}m")


def reap_once(dry: bool) -> None:
    running = running_containers()
    for name, home in AGENTS.items():
        if name not in running:
            continue
        idle = seconds_idle(home)
        if idle is None:
            continue                               # no signal — don't guess
        if idle >= IDLE_TIMEOUT_S:
            if dry:
                print(f"[reaper:dry] would stop {name}: idle {int(idle // 60)}m")
            else:
                stop_container(name, int(idle // 60))


# ---- wake ---------------------------------------------------------------

def wake(name: str) -> None:
    if name in ALWAYS_ON:
        return
    full = name if name in AGENTS else f"agent-office-{name}"
    if full not in AGENTS:
        print(f"[reaper] wake: unknown '{name}'", flush=True)
        return
    if full in running_containers():
        return
    print(f"[reaper] waking {full}", flush=True)
    sh(["docker", "start", full])
    emit("agent.started", name, "wake")


def listen_wakes() -> None:
    """Subscribe to office:inbox:* and handle agent.wake envelopes.

    BusClient's socket timeout is 5s; PSUBSCRIBE blocks forever, so expect
    periodic timeouts and just reconnect (messages during the gap are lost —
    acceptable for wake signals, senders retry via door).
    """
    sys.path.insert(0, str(REPO / "office"))
    from bus.client import BusClient
    while True:
        try:
            bus = BusClient()
            for _ch, msg in bus.psubscribe(["office:inbox:*"]):
                try:
                    env = json.loads(msg)
                    if env.get("action") == "agent.wake":
                        wake(env.get("target") or "")
                except Exception as exc:
                    print(f"[reaper] bad inbox msg: {exc}", flush=True)
        except Exception:
            time.sleep(2)                          # quiet reconnect loop


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"[reaper] online: timeout={IDLE_TIMEOUT_S}s interval={CHECK_INTERVAL}s "
          f"dry={dry}", flush=True)
    threading.Thread(target=listen_wakes, daemon=True).start()
    while True:
        try:
            reap_once(dry)
        except Exception as exc:
            print(f"[reaper] reap error: {exc}", flush=True)
        time.sleep(CHECK_INTERVAL)

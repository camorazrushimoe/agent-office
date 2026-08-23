#!/usr/bin/env python3
"""Agent Office — lifecycle controller, docker mode.

Docker twin of the native controller: identical bus contract
(state keys, busy locks, last_active, agent.started/stopped/wake_failed)
but manages *containers* instead of host processes via docker.sock,
scoped to this compose project (COMPOSE_PROJECT label filter) so it can
never touch other projects' containers.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from bus.client import EVENTS_CHANNEL, BusClient, make_envelope, now_iso  # noqa: E402

IDLE_TIMEOUT = _env_s = os.environ.get("IDLE_TIMEOUT", "40m")
WAKE_TIMEOUT = float(os.environ.get("WAKE_TIMEOUT_S") or 90)
STOP_CHECK_INTERVAL = float(os.environ.get("STOP_CHECK_INTERVAL", 120))
COMPOSE_PROJECT = os.environ.get("COMPOSE_PROJECT", "agent-office")


def parse_duration(s: str | float) -> float:
    if isinstance(s, (int, float)):
        return float(s)
    s = s.strip().lower()
    if s.endswith("m"):
        return float(s[:-1]) * 60
    if s.endswith("h"):
        return float(s[:-1]) * 3600
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


IDLE_TIMEOUT = parse_duration(_env_s)


class DockerAPI:
    """Tiny urllib client for the Docker Engine API over unix socket."""

    def __init__(self, sock_path: str = "/var/run/docker.sock"):
        self.sock_path = sock_path

    def _request(self, method: str, path: str, body: dict | None = None):
        import socket as pysocket

        raw = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"http://localhost{path}", data=raw, method=method
        )
        if raw:
            req.add_header("Content-Type", "application/json")

        class UnixConnection(pysocket.socket):
            pass

        # urllib has no unix-socket transport; use a minimal handoff via
        # http.client over a socket file descriptor.
        import http.client

        class UnixHTTPConnection(http.client.HTTPConnection):
            def __init__(self, path):
                super().__init__("localhost")
                self._path = path

            def connect(self):
                self.sock = pysocket.socket(pysocket.AF_UNIX, pysocket.SOCK_STREAM)
                self.sock.connect(self._path)

        conn = UnixHTTPConnection(self.sock_path)
        conn.request(method, path, body=raw,
                     headers={"Content-Type": "application/json"} if raw else {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        if resp.status >= 400:
            raise RuntimeError(f"docker api {method} {path}: {resp.status} {data[:200]!r}")
        return json.loads(data) if data else None


class DockerLifecycle:
    STATE_KEY = "office:state:{agent}"
    BUSY_KEY = "office:busy:{agent}"
    LASTACTIVE_KEY = "office:last_active:{agent}"

    def __init__(self):
        self.bus = BusClient()
        self.docker = DockerAPI()
        self.agents = self._load_agents()

    def _load_agents(self) -> dict[str, dict]:
        path = Path("/opt/registry/agents.json")
        if not path.exists():
            path = HERE.parent.parent / "registry" / "agents.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {a["id"]: a for a in raw.get("agents", [])}

    # ---- container helpers ------------------------------------------

    @staticmethod
    def container_name(agent_id: str) -> str:
        return f"agent-office-{agent_id}"

    def inspect(self, agent_id: str) -> dict | None:
        try:
            info = self.docker._request(
                "GET", f"/containers/{self.container_name(agent_id)}/json"
            )
            return info
        except RuntimeError:
            return None

    def is_running(self, agent_id: str) -> bool:
        info = self.inspect(agent_id)
        if not info:
            return False
        state = info.get("State", {})
        return bool(state.get("Running")) and not bool(state.get("Paused"))

    def start_agent(self, agent_id: str) -> None:
        self.docker._request("POST", f"/containers/{self.container_name(agent_id)}/start")

    def stop_agent(self, agent_id: str, timeout: int = 10) -> None:
        self.docker._request(
            "POST", f"/containers/{self.container_name(agent_id)}/stop?t={timeout}"
        )

    # ---- state ------------------------------------------------------

    def get_state(self, agent_id: str) -> str:
        if not self.is_running(agent_id):
            return "stopped"
        return self.bus.get_key(self.STATE_KEY.format(agent=agent_id)) or "running"

    def set_state(self, agent_id: str, state: str) -> None:
        self.bus.set_key(self.STATE_KEY.format(agent=agent_id), state)

    def touch(self, agent_id: str) -> None:
        self.bus.set_key(self.LASTACTIVE_KEY.format(agent=agent_id), now_iso())

    # ---- events -----------------------------------------------------

    def emit(self, action: str, agent_id: str, summary: str) -> None:
        env = make_envelope(
            actor="lifecycle",
            action=action,
            target=agent_id,
            payload={"summary": summary},
        )
        try:
            self.bus.publish(EVENTS_CHANNEL, json.dumps(env, ensure_ascii=False))
        except Exception as exc:
            print(f"[lifecycle] bus publish failed: {exc}", flush=True)
        print(f"[lifecycle] {action} {agent_id}: {summary}", flush=True)

    # ---- wake -------------------------------------------------------

    def wake(self, agent_id: str, reason: str = "") -> tuple[bool, str]:
        if agent_id not in self.agents:
            return False, f"unknown agent '{agent_id}'"
        if self.is_running(agent_id):
            self.touch(agent_id)
            return True, "already running"
        self.set_state(agent_id, "starting")
        try:
            self.start_agent(agent_id)
        except Exception as exc:
            self.set_state(agent_id, "stopped")
            self.emit("agent.wake_failed", agent_id, f"start failed: {exc}")
            return False, f"start failed: {exc}"

        deadline = time.time() + WAKE_TIMEOUT
        while time.time() < deadline:
            if self.is_running(agent_id):
                self.set_state(agent_id, "running")
                self.touch(agent_id)
                self.emit("agent.started", agent_id, reason or "wake")
                return True, "started"
            time.sleep(0.5)
        self.set_state(agent_id, "stopped")
        self.emit("agent.wake_failed", agent_id, f"wake timeout after {int(WAKE_TIMEOUT)}s")
        return False, "wake timeout"

    # ---- idle reaper ------------------------------------------------

    def reap_idle(self) -> None:
        for agent_id in self.agents:
            if not self.is_running(agent_id):
                continue
            if self.bus.get_key(self.BUSY_KEY.format(agent=agent_id)):
                continue
            last = self.bus.get_key(self.LASTACTIVE_KEY.format(agent=agent_id))
            if not last:
                continue
            from datetime import datetime

            idle_s = time.time() - datetime.fromisoformat(last).timestamp()
            if idle_s >= IDLE_TIMEOUT:
                idle_min = int(idle_s // 60)
                self.set_state(agent_id, "stopping")
                try:
                    self.stop_agent(agent_id)
                except Exception as exc:
                    print(f"[lifecycle] stop {agent_id}: {exc}", flush=True)
                self.set_state(agent_id, "stopped")
                self.emit(
                    "agent.stopped",
                    agent_id,
                    f"idle {idle_min}m >= {int(IDLE_TIMEOUT) // 60}m",
                )

    # ---- main loop --------------------------------------------------

    def run_forever(self) -> None:
        self.emit("lifecycle.started", "*", "docker lifecycle controller online")

        import threading

        INBOX_PREFIX = "office:inbox:"

        def subscriber():
            while True:
                try:
                    for _channel, message in self.bus.subscribe([INBOX_PREFIX + "*"]):
                        try:
                            env = json.loads(message)
                            if env.get("action") == "agent.wake":
                                target = env.get("target")
                                ok, note = self.wake(
                                    target, env.get("payload", {}).get("reason", "")
                                )
                                if not ok:
                                    print(f"[lifecycle] wake {target}: {note}", flush=True)
                        except Exception as exc:
                            print(f"[lifecycle] bad inbox msg: {exc}", flush=True)
                except Exception as exc:
                    print(f"[lifecycle] subscribe error: {exc}; retrying", flush=True)
                    time.sleep(2)

        threading.Thread(target=subscriber, daemon=True).start()
        while True:
            time.sleep(STOP_CHECK_INTERVAL)
            try:
                self.reap_idle()
            except Exception as exc:
                print(f"[lifecycle] reap error: {exc}", flush=True)


if __name__ == "__main__":
    DockerLifecycle().run_forever()

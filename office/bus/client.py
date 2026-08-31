#!/usr/bin/env python3
"""Agent Office — shared bus client (Redis-backed, stdlib-only RESP).

Single shared Redis bus at Office level. All Office agents and all team
agents connect to this bus. This module is the ONLY place that knows the
wire details; everything else uses BusClient / publish() / subscribe().

Envelope schema: bus/action-schema.json (id/actor/action/target/timestamp).
Channels:
  office:events      — all action envelopes (event log source of truth)
  office:inbox:{agent_id} — direct wake/delivery signal per agent

Stdlib only (no redis-py dependency): implements the tiny RESP subset we
need (CONNECT, AUTH, SELECT, PUBLISH, SUBSCRIBE, PING, SET, GET, DEL,
EXPIRE, HSET, HGET, KEYS) so it runs in any environment.
"""
from __future__ import annotations

import datetime
import json
import os
import socket
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

DEFAULT_BUS_URL = os.environ.get("OFFICE_BUS_URL", "redis://127.0.0.1:6380/0")
EVENTS_CHANNEL = "office:events:topic"   # pub/sub fanout for live followers
EVENTS_STREAM = "office:events"          # Redis STREAM — durable event log
INBOX_PREFIX = "office:inbox:"
STATE_PREFIX = "office:state:"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "bus" / "action-schema.json"


def _parse_redis_url(url: str) -> dict:
    # redis://[:password@]host:port/db
    rest = url[len("redis://"):]
    password = None
    if "@" in rest:
        cred, rest = rest.rsplit("@", 1)
        password = cred.split(":", 1)[1] if ":" in cred else cred
    db = 0
    if "/" in rest:
        rest, _, db_s = rest.partition("/")
        try:
            db = int(db_s)
        except ValueError:
            db = 0
    host, _, port_s = rest.partition(":")
    return {"host": host or "127.0.0.1", "port": int(port_s or 6379),
            "password": password, "db": db}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


class BusError(RuntimeError):
    pass


class BusClient:
    """Minimal synchronous Redis client speaking RESP directly.

    Good enough for the Office skeleton: one connection per operation for
    commands, a dedicated socket for SUBSCRIBE loops.
    """

    def __init__(self, url: str | None = None, timeout: float = 5.0):
        self._url = url or DEFAULT_BUS_URL
        self._timeout = timeout
        self._conn: dict = _parse_redis_url(self._url)

    # ---- low-level RESP -------------------------------------------------

    def _connect(self) -> "socket.socket":
        sock = socket.create_connection(
            (self._conn["host"], self._conn["port"]), timeout=self._timeout
        )
        reader = sock.makefile("rb")
        if self._conn.get("password"):
            self._command(reader, sock, "AUTH", self._conn["password"])
        if self._conn.get("db"):
            self._command(reader, sock, "SELECT", str(self._conn["db"]))
        return sock

    @staticmethod
    def _read(f) -> Any:
        line = f.readline()
        if not line:
            raise BusError("connection closed")
        t, payload = line[:1], line[1:-2]
        if t == b"+":
            return payload.decode()
        if t == b"-":
            raise BusError(payload.decode())
        if t == b":":
            return int(payload)
        if t == b"$":
            n = int(payload)
            if n == -1:
                return None
            data = f.read(n + 2)
            return data[:-2].decode()
        if t == b"*":
            n = int(payload)
            if n == -1:
                return None
            return [BusClient._read(f) for _ in range(n)]
        raise BusError(f"bad RESP line: {line!r}")

    def _send(self, writer, *args: Any) -> None:
        out = [b"*" + str(len(args)).encode() + b"\r\n"]
        for a in args:
            b = a.encode() if isinstance(a, str) else a
            out.append(b"$" + str(len(b)).encode() + b"\r\n" + b + b"\r\n")
        writer.write(b"".join(out))
        writer.flush()

    def _command(self, reader, sock, *args: Any) -> Any:
        writer = sock.makefile("wb")
        self._send(writer, *args)
        return self._read(reader)

    def cmd(self, *args: Any) -> Any:
        """Execute one command on a fresh connection."""
        sock = self._connect()
        try:
            reader = sock.makefile("rb")
            return self._command(reader, sock, *args)
        finally:
            sock.close()

    def pipeline_cmds(self, *commands: tuple) -> list:
        """Execute several commands over one connection."""
        sock = self._connect()
        results = []
        try:
            reader = sock.makefile("rb")
            for c in commands:
                results.append(self._command(reader, sock, *c))
        finally:
            sock.close()
        return results

    # ---- public API ------------------------------------------------------

    def ping(self) -> bool:
        try:
            return self.cmd("PING") == "PONG"
        except Exception:
            return False

    def set_key(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl:
            self.cmd("SET", key, value, "EX", str(ttl))
        else:
            self.cmd("SET", key, value)

    def get_key(self, key: str) -> str | None:
        return self.cmd("GET", key)

    def del_key(self, key: str) -> None:
        self.cmd("DEL", key)

    def hset(self, key: str, field: str, value: str) -> None:
        self.cmd("HSET", key, field, value)

    def hgetall(self, key: str) -> dict:
        res = self.cmd("HGETALL", key) or []
        return {res[i]: res[i + 1] for i in range(0, len(res), 2)}

    def keys(self, pattern: str) -> list[str]:
        return self.cmd("KEYS", pattern) or []

    def publish(self, channel: str, payload_json: str) -> int:
        return int(self.cmd("PUBLISH", channel, payload_json))

    def xread(self, key: str, last_id: str, count: int = 100) -> list[tuple[str, dict]]:
        """Non-blocking XREAD of a Redis stream after `last_id`.

        Returns [(entry_id, fields_dict), ...] in stream order (oldest first),
        newest last — ready for high-water-mark tracking. Empty when the
        stream has no new entries.
        """
        reply = self.cmd("XREAD", "COUNT", str(count), "STREAMS", key, last_id)
        out: list[tuple[str, dict]] = []
        if not reply:
            return out
        # reply: [[stream_name, [[id, [f1, v1, ...]], ...]], ...]
        for stream in reply:
            if not isinstance(stream, list) or len(stream) < 2:
                continue
            entries = stream[1]
            if not entries:
                continue
            for entry in entries:
                if not isinstance(entry, list) or len(entry) < 2:
                    continue
                eid, flat = entry[0], entry[1]
                fields: dict = {}
                for i in range(0, len(flat) - 1, 2):
                    fields[flat[i]] = flat[i + 1]
                out.append((eid, fields))
        return out

    def xrevrange_tail(self, key: str) -> str | None:
        """ID of the newest stream entry, or None when the stream is empty.

        Used to seed a durable re-scan from a concrete position (not "$") on
        first boot, so a later restart resumes from a real stream id.
        """
        reply = self.cmd("XREVRANGE", key, "+", "-", "COUNT", "1")
        # reply: [[id, [f1, v1, ...]], ...] or []
        if not reply or not isinstance(reply[0], list) or len(reply[0]) < 1:
            return None
        return reply[0][0]

    def psubscribe(self, patterns: list[str]) -> Iterator[tuple[str, str]]:
        """Blocking generator yielding (pattern, channel, message)-style
        tuples (channel, message) matched via PSUBSCRIBE glob patterns."""
        import threading

        while True:
            sock = self._connect()
            try:
                reader = sock.makefile("rb")
                writer = sock.makefile("wb")
                self._send(writer, "PSUBSCRIBE", *patterns)
                ack = self._read(reader)
                stop = threading.Event()

                def watchdog():
                    while not stop.wait(25.0):
                        try:
                            self._send(writer, "PING")
                            writer.flush()
                        except Exception:
                            return

                threading.Thread(target=watchdog, daemon=True).start()
                try:
                    while True:
                        msg = self._read(reader)
                        # pmessage = [b"pmessage", pattern, channel, payload]
                        if isinstance(msg, list) and msg[0] == "pmessage" and len(msg) >= 4:
                            yield msg[2], msg[3]
                finally:
                    stop.set()
            finally:
                sock.close()

    def subscribe(self, channels: list[str]) -> Iterator[tuple[str, str]]:
        """Blocking generator yielding (channel, message).

        Sends PINGs on a watchdog thread to defeat Redis' idle timeout
        (default 0 = none, but some sandboxes/proxies time out idle
        connections aggressively); on timeout the connection is rebuilt.
        """
        import threading

        while True:
            sock = self._connect()
            try:
                reader = sock.makefile("rb")
                writer = sock.makefile("wb")
                self._send(writer, "SUBSCRIBE", *channels)
                ack = self._read(reader)  # subscribe confirmation
                stop = threading.Event()

                def watchdog():
                    while not stop.wait(25.0):
                        try:
                            # Interleaved commands on a subscriber connection
                            # are allowed for PING; reply arrives as a push
                            # message we skip in the loop below.
                            self._send(writer, "PING")
                            writer.flush()
                        except Exception:
                            return

                threading.Thread(target=watchdog, daemon=True).start()
                try:
                    while True:
                        msg = self._read(reader)
                        if isinstance(msg, list) and len(msg) >= 3 and msg[0] == "message":
                            yield msg[1], msg[2]
                finally:
                    stop.set()
            finally:
                sock.close()


# ---- envelope helpers ----------------------------------------------------


def make_envelope(
    actor: str,
    action: str,
    target: str = "*",
    *,
    team: str | None = None,
    project: str | None = None,
    payload: dict | None = None,
    summary: str | None = None,
) -> dict:
    """Build an action envelope per bus/action-schema.json."""
    env = {
        "id": str(uuid.uuid4()),
        "actor": actor,
        "action": action,
        "target": target,
        "timestamp": now_iso(),
    }
    if team:
        env["team"] = team
    if project:
        env["project"] = project
    if payload is not None:
        env["payload"] = payload
    if summary:
        # Observability spec: events SHOULD carry a short human-readable
        # summary. Stored inside the envelope as payload.summary when no
        # structured payload is given.
        if payload is None:
            env["payload"] = {"summary": summary}
        else:
            env["payload"] = {**payload, "summary": summary}
    return env


def validate_envelope(env: dict) -> list[str]:
    """Validate against the required fields of bus/action-schema.json."""
    errors = []
    for field in ("id", "actor", "action", "target", "timestamp"):
        if not env.get(field):
            errors.append(f"missing required field: {field}")
    return errors


def publish_event(bus: BusClient, envelope: dict) -> int:
    """Publish an envelope to the durable stream AND the live fanout topic.

    Durable layer mirrors upstream's contract: XADD office:events with
    fields (action/actor/target/timestamp/summary...) so crew/office-log.py
    reads our events natively. The pub/sub topic serves --follow followers.
    """
    errs = validate_envelope(envelope)
    if errs:
        raise BusError("; ".join(errs))
    payload_json = json.dumps(envelope, ensure_ascii=False)
    summary = (envelope.get("payload") or {}).get("summary", "")
    bus.pipeline_cmds(
        (
            "XADD",
            EVENTS_STREAM,
            "*",
            "action",
            envelope["action"],
            "actor",
            envelope["actor"],
            "target",
            envelope.get("target", "*"),
            "timestamp",
            envelope["timestamp"],
            "project",
            envelope.get("project", ""),
            "team",
            envelope.get("team", ""),
            "summary",
            str(summary),
            "json",
            payload_json,
        ),
        ("PUBLISH", EVENTS_CHANNEL, payload_json),
    )
    return 1


def send_wake(bus: BusClient, agent_id: str, reason: str = "",
              actor: str = "lifecycle") -> int:
    """Publish an agent.wake request targeted at one agent."""
    env = make_envelope(
        actor=actor,
        action="agent.wake",
        target=agent_id,
        payload={"reason": reason} if reason else None,
    )
    published = publish_event(bus, env)
    published += bus.publish(INBOX_PREFIX + agent_id, json.dumps(env))
    return published


if __name__ == "__main__":
    import sys

    c = BusClient()
    if not c.ping():
        print("bus unreachable:", DEFAULT_BUS_URL)
        sys.exit(1)
    print("bus OK on", DEFAULT_BUS_URL)

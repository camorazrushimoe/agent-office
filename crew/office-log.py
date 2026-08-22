#!/usr/bin/env python3
"""Agent Office — CLI event log (Redis stream / list tail).

Reads high-level events from the shared Office Redis bus.

Default stream key: office:events (Redis STREAM).
Fallback: if the stream is empty, also checks list key office:events:list.

Usage:
  python3 crew/office-log.py
  python3 crew/office-log.py --follow
  python3 crew/office-log.py --project my-proj
  python3 crew/office-log.py --team dev-1
  python3 crew/office-log.py --count 50

Env:
  OFFICE_BUS_URL  default redis://127.0.0.1:6380

Publish test event (redis-cli):
  redis-cli -p 6380 XADD office:events * action agent.online actor system summary "office up"

Stdlib only (TCP RESP subset for XREVRANGE / XREAD / LRANGE).
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from urllib.parse import urlparse

STREAM = "office:events"
LIST_KEY = "office:events:list"


def parse_bus_url(url: str) -> tuple[str, int, int]:
    u = urlparse(url)
    host = u.hostname or "127.0.0.1"
    port = u.port or 6379
    db = 0
    if u.path and len(u.path) > 1 and u.path[1:].isdigit():
        db = int(u.path[1:])
    return host, port, db


class RedisLite:
    """Minimal Redis client for stream/list read (enough for office-log)."""

    def __init__(self, host: str, port: int, db: int = 0):
        self.sock = socket.create_connection((host, port), timeout=10)
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

    def _read_reply(self):
        line = self.file.readline()
        if not line:
            raise ConnectionError("Redis connection closed")
        prefix = line[:1]
        if prefix == b"+":
            return line[1:-2].decode()
        if prefix == b"-":
            raise RuntimeError(line[1:-2].decode())
        if prefix == b":":
            return int(line[1:-2])
        if prefix == b"$":
            n = int(line[1:-2])
            if n == -1:
                return None
            data = self.file.read(n + 2)[:-2]
            return data.decode("utf-8", errors="replace")
        if prefix == b"*":
            n = int(line[1:-2])
            if n == -1:
                return None
            return [self._read_reply() for _ in range(n)]
        raise RuntimeError(f"Unknown RESP: {line!r}")

    def _call(self, *parts: str):
        self.sock.sendall(self._encode(*parts))
        return self._read_reply()

    def xrevrange(self, key: str, count: int):
        return self._call("XREVRANGE", key, "+", "-", "COUNT", str(count))

    def xread_block(self, key: str, last_id: str, block_ms: int):
        return self._call(
            "XREAD", "BLOCK", str(block_ms), "COUNT", "20", "STREAMS", key, last_id
        )

    def lrange(self, key: str, start: int, stop: int):
        return self._call("LRANGE", key, str(start), str(stop))


def pairs_to_dict(flat):
    if not flat:
        return {}
    d = {}
    for i in range(0, len(flat), 2):
        if i + 1 < len(flat):
            d[flat[i]] = flat[i + 1]
    return d


def format_event(entry_id: str, fields: dict) -> str:
    action = fields.get("action", "?")
    actor = fields.get("actor", "?")
    summary = fields.get("summary") or fields.get("message") or ""
    project = fields.get("project", "")
    team = fields.get("team", "")
    ts = fields.get("timestamp", entry_id)
    bits = [f"[{ts}]", f"{actor}", action]
    if team:
        bits.append(f"team={team}")
    if project:
        bits.append(f"project={project}")
    if summary:
        bits.append(summary)
    return " ".join(bits)


def filter_fields(fields: dict, project: str | None, team: str | None) -> bool:
    if project and fields.get("project") != project:
        return False
    if team and fields.get("team") != team:
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Agent Office CLI event log")
    ap.add_argument("--follow", "-f", action="store_true")
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--project", default=None)
    ap.add_argument("--team", default=None)
    ap.add_argument(
        "--url",
        default=os.environ.get("OFFICE_BUS_URL", "redis://127.0.0.1:6380"),
    )
    args = ap.parse_args()

    host, port, db = parse_bus_url(args.url)
    try:
        r = RedisLite(host, port, db)
    except OSError as e:
        print(f"Cannot connect to Redis at {host}:{port}: {e}", file=sys.stderr)
        print("Is Office up? docker compose up -d", file=sys.stderr)
        sys.exit(1)

    try:
        rows = r.xrevrange(STREAM, args.count) or []
        # XREVRANGE returns newest first; print chronological
        events = []
        for row in rows:
            if not row or len(row) < 2:
                continue
            eid, flat = row[0], row[1]
            fields = pairs_to_dict(flat)
            if filter_fields(fields, args.project, args.team):
                events.append((eid, fields))
        events.reverse()
        if not events:
            # fallback list
            listed = r.lrange(LIST_KEY, -args.count, -1) or []
            for item in listed:
                print(item)
            if not listed:
                print(
                    f"(no events on stream '{STREAM}' yet — Office is up if Redis answers)"
                )
        else:
            for eid, fields in events:
                print(format_event(eid, fields))

        if args.follow:
            last = events[-1][0] if events else "$"
            print("--- follow (Ctrl+C to stop) ---")
            while True:
                try:
                    reply = r.xread_block(STREAM, last, 5000)
                except KeyboardInterrupt:
                    break
                if not reply:
                    continue
                # [[stream, [[id, fields], ...]]]
                for _stream, entries in reply:
                    for eid, flat in entries:
                        fields = pairs_to_dict(flat)
                        last = eid
                        if filter_fields(fields, args.project, args.team):
                            print(format_event(eid, fields), flush=True)
    finally:
        r.close()


if __name__ == "__main__":
    main()

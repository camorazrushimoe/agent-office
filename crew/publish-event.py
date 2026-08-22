#!/usr/bin/env python3
"""Publish a structured event to the Office Redis stream office:events.

Usage:
  python3 crew/publish-event.py agent.online system "office shell up"
  python3 crew/publish-event.py project.created scrum-master "new idea" --project demo --team lab-1

Env: OFFICE_BUS_URL (default redis://127.0.0.1:6380)
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

STREAM = "office:events"


def parse_bus_url(url: str) -> tuple[str, int, int]:
    u = urlparse(url)
    host = u.hostname or "127.0.0.1"
    port = u.port or 6379
    db = 0
    if u.path and len(u.path) > 1 and u.path[1:].isdigit():
        db = int(u.path[1:])
    return host, port, db


def redis_xadd(host: str, port: int, db: int, fields: dict) -> str:
    sock = socket.create_connection((host, port), timeout=10)
    f = sock.makefile("rb")

    def call(*parts: str):
        buf = [f"*{len(parts)}\r\n".encode()]
        for p in parts:
            b = p.encode("utf-8")
            buf.append(f"${len(b)}\r\n".encode())
            buf.append(b)
            buf.append(b"\r\n")
        sock.sendall(b"".join(buf))
        line = f.readline()
        if line.startswith(b"-"):
            raise RuntimeError(line[1:-2].decode())
        if line.startswith(b"$"):
            n = int(line[1:-2])
            data = f.read(n + 2)[:-2]
            return data.decode()
        if line.startswith(b"+"):
            return line[1:-2].decode()
        return line.decode()

    if db:
        call("SELECT", str(db))
    args = ["XADD", STREAM, "*"]
    for k, v in fields.items():
        if v is not None and v != "":
            args.extend([k, str(v)])
    eid = call(*args)
    sock.close()
    return eid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action")
    ap.add_argument("actor")
    ap.add_argument("summary")
    ap.add_argument("--project", default="")
    ap.add_argument("--team", default="")
    ap.add_argument("--target", default="*")
    ap.add_argument(
        "--url", default=os.environ.get("OFFICE_BUS_URL", "redis://127.0.0.1:6380")
    )
    args = ap.parse_args()
    host, port, db = parse_bus_url(args.url)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = {
        "action": args.action,
        "actor": args.actor,
        "summary": args.summary,
        "target": args.target,
        "timestamp": ts,
        "project": args.project,
        "team": args.team,
    }
    try:
        eid = redis_xadd(host, port, db, fields)
    except OSError as e:
        print(f"Redis error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"published {eid} {args.action} by {args.actor}")


if __name__ == "__main__":
    main()

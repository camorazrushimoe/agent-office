#!/usr/bin/env python3
"""Agent Office — bus recorder.

Derives the durable event log from the live bus (docs/observability.md):
subscribes to office:events and appends every envelope to logs/events.jsonl.
This is the always-on thin helper; the CLI reads its output.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

OFFICE_HOME = Path("/opt/office-home")  # container mount of the office repo
if not OFFICE_HOME.exists():
    OFFICE_HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OFFICE_HOME / "office"))
from bus.client import EVENTS_CHANNEL, BusClient  # noqa: E402

LOG_PATH = OFFICE_HOME / "logs" / "events.jsonl"


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    while True:
        bus = BusClient()
        if not bus.ping():
            print("[recorder] bus unreachable; retrying in 3s", flush=True)
            time.sleep(3)
            continue
        try:
            for _channel, message in bus.subscribe([EVENTS_CHANNEL]):
                with open(LOG_PATH, "a", encoding="utf-8") as fh:
                    fh.write(message.rstrip("\n") + "\n")
        except KeyboardInterrupt:
            print("[recorder] bye")
            return
        except Exception as exc:
            print(f"[recorder] error: {exc}; reconnecting", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()

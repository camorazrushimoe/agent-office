#!/usr/bin/env python3
"""Office bus publisher for spec-team agents (copy into the shared workspace).

Uses the Office stdlib client at /opt/office-lib/bus/client.py — no redis-py.
Publishes one envelope to the durable stream (office:events) AND the live
topic (office:events:topic) via publish_event(), per the Office observability
contract.

usage:
  bus_publish.py <action> [payload_json] [project] [actor] [team]

examples:
  bus_publish.py pipeline.started '{"intake_id":"i-1"}' my-project
  bus_publish.py intake.classified '{...}' my-project spec-1/technical-product-manager spec-1

Reads OFFICE_BUS_URL from the environment (do not override — the module
default is not the Office bus).
"""
import sys, json

OFFICE_LIB = "/opt/office-lib"  # adjust if the deployment mounts it elsewhere
sys.path.insert(0, OFFICE_LIB)
from bus.client import BusClient, make_envelope, publish_event  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("usage: bus_publish.py <action> [payload_json] [project] [actor] [team]")
        sys.exit(2)
    action = sys.argv[1]
    payload = json.loads(sys.argv[2]) if (len(sys.argv) > 2 and sys.argv[2].strip()) else None
    project = sys.argv[3] if len(sys.argv) > 3 else None
    actor = sys.argv[4] if len(sys.argv) > 4 else "spec-1/technical-product-manager"
    team = sys.argv[5] if len(sys.argv) > 5 else "spec-1"

    env = make_envelope(actor=actor, action=action, target="*",
                        team=team, project=project, payload=payload)
    bus = BusClient()
    if not bus.ping():
        print("ERROR: bus unreachable at", bus._url)
        sys.exit(1)
    publish_event(bus, env)
    print("PUBLISHED", action, "id=", env["id"], "ts=", env["timestamp"])


if __name__ == "__main__":
    main()

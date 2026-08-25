# Office Bus — Wire Details

Source of truth: `/opt/office-lib/bus/client.py` (stdlib-only RESP client, no
redis-py) + `product-factory/bus/action-schema.json` +
`agent-office/docs/observability.md`.

## Channels & keys
- `office:events` — Redis STREAM, durable event log (XADD). The source of
  truth; `crew/office-log.py` and Scrum Master status views read this.
- `office:events:topic` — pub/sub fanout for live followers (`--follow`).
- `office:inbox:<agent_id>` — direct wake/delivery signal per agent.
- `office:state:*` — lifecycle state (running/stopped, last_active, busy
  lock `agent:<id>:busy`).

## Envelope
```json
{
  "id": "<uuid4>",
  "actor": "spec-1/technical-product-manager",
  "action": "intake.classified",
  "target": "*",
  "timestamp": "2026-08-24T18:13:30.664+00:00",
  "team": "spec-1",
  "project": "vk-monitoring-service",
  "payload": {
    "summary": "short human-readable one-liner (observability spec)",
    "...": "structured fields",
    "links": ["workspace/specs/my-spec.md"]
  }
}
```
Required (validated, publish raises if missing): `id`, `actor`, `action`,
`target`, `timestamp`. `publish_event()` XADDs a flattened projection
(action/actor/target/timestamp/project/team/summary + full `json`) AND
PUBLISHes the envelope to the topic in one pipeline.

## Quick publish (ad-hoc, no script file)
```python
import sys; sys.path.insert(0, "/opt/office-lib")
from bus.client import BusClient, make_envelope, publish_event
bus = BusClient()                      # reads $OFFICE_BUS_URL
env = make_envelope(
    actor="spec-1/technical-product-manager",
    action="wiki.updated",
    team="spec-1",
    project="my-project",
    payload={"summary": "added research package", "pages": ["sources/x.md"]},
)
publish_event(bus, env)                # raises BusError if invalid
```

## Verify after publishing (MANDATORY)
`publish_event` returning is not proof. Read back the stream:
```python
import sys; sys.path.insert(0, "/opt/office-lib")
from bus.client import BusClient
b = BusClient()
print("XLEN", b.cmd("XLEN", "office:events"))
sock = b._connect(); r = sock.makefile("rb"); w = sock.makefile("wb")
b._send(w, "XREVRANGE", "office:events", "+", "-", "COUNT", "10")
rows = b._read(r)
# rows: [ [entry_id, [k, v, k, v, ...]], ... ]
for row in rows:
    f = dict(zip(row[1][::2], row[1][1::2]))
    print(f.get("timestamp", "")[11:19], f.get("actor"), f.get("action"))
```
Parsing gotcha: `row[1]` is the flat `[field, value, field, value, ...]`
list — zip evens with odds. (First attempt in the 2026-08-24 run mis-parsed
rows as pairs of rows and printed blank lines.)

## Waking an agent (lifecycle)
```python
from bus.client import BusClient, send_wake
send_wake(BusClient(), "spec-1-product-researcher", reason="door-send: TPM handoff")
```
The lifecycle controller (separate container) performs the docker start;
wait for the target's `/health` to return 200 before POSTing (WAKE_TIMEOUT
default 90s). If wake fails, fail the send explicitly — never silently drop.

## Gotchas
- One connection per `cmd()`; use `pipeline_cmds()` for multi-command writes.
- `subscribe()`/`psubscribe()` are blocking generators with a PING watchdog;
  don't hold them in a short script.
- Bus URL comes from `OFFICE_BUS_URL`; the module default
  (`redis://127.0.0.1:6380/0`) is NOT the Office bus — always rely on env.
- `KEYS office:*` is fine at this scale; avoid on a hot path.

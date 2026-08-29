# Design — Scrum Master control plane

## 1. The core insight

Hermes **already has** the two hooks we need. Every agent's
`hermes-home/hooks/` directory exists and is empty; it is the home for
*gateway event hooks* (`HOOK.yaml` + `handler.py`). Two lifecycle events map
1:1 onto the two moments we care about:

| Hook | Hermes event | Meaning | Fires when |
|------|-------------|---------|------------|
| `task-accepted` | `agent:start` | agent got a task and went to work | the model begins processing an inbound message |
| `task-stopped`  | `agent:end`   | the model stopped working | the model finishes and returns a response |

So **no new core plumbing is needed** — this is config + a thin handler per
agent, not a runtime change.

### Handler context (what we get for free)

- `agent:start`: `platform`, `user_id`, `chat_id`, `thread_id`, `chat_type`,
  `session_id`, `message` (truncated to 500 chars).
- `agent:end`: same keys + `response` (truncated to 500 chars), `model`,
  `provider`.

### Hard guarantees (and their limits)

- Hooks are **observer-only and failure-isolated**: a broken hook is caught
  and logged, never blocks or alters the agent's turn. That is the "fires
  100% of the time without breaking anything" property.
- Hooks fire on the **normal** start/stop path. They do **not** fire if the
  container is OOM-killed or `docker stop`ped mid-turn — that is precisely the
  gap the *stale-heartbeat* check closes (§5).
- Gateway event hooks fire only in **gateway mode**. All Office + team agents
  here are always-on gateway processes (they receive work through the webhook
  door / bus), so this is fine; if an agent is ever run one-shot via CLI, the
  board shows a gap rather than a false state. This limitation is acceptable
  for v1 and is documented.

## 2. Architecture

```
                 ┌────────────────────────────────────────────┐
                 │  each agent (gateway process)              │
                 │  hooks/task-accepted  -> task.started      │
                 │  hooks/task-stopped   -> task.finished     │
                 │  (SOUL convention)    -> task.finished|blocked (rich) │
                 └───────────────┬────────────────────────────┘
                                 │ publish_event()  (fire-and-forget)
                                 ▼
                       ┌─────────────────────┐
                       │  Redis bus          │  office:events (durable stream)
                       └─────────┬───────────┘
                                 │ subscribe (single consumer)
                                 ▼
                       ┌─────────────────────┐
                       │  scrum-board writer │  always-on, ONE writer
                       │  office/scrum/board.py │
                       └─────────┬───────────┘
                                 │ materialise
                                 ▼
                       ┌─────────────────────┐
                       │  board.json         │  current state + rolling window
                       └─────────┬───────────┘
                                 │ read
                                 ▼
                       ┌─────────────────────┐
                       │  Scrum Master (LLM) │  controller: stall check,
                       │  cron + skill       │  escalation point, hygiene
                       └─────────────────────┘
```

### Why "one writer", not "hooks write the JSON directly"

16 agents in 16 containers all appending to one JSON file = lost updates,
interleaved writes, corrupted JSON. There is no cross-container file lock.

The bus is already the single durable source of truth (Redis stream), and the
repo already has the *single-consumer → materialised view* pattern
(`office/bus/recorder.py` subscribes and appends to `logs/events.jsonl`). We
reuse exactly that pattern: hooks publish envelopes (cheap, non-blocking),
and **one** board writer maintains the JSON. The JSON the user wants is a
*view*; the bus is the source of truth.

## 3. The two hooks (deterministic layer)

Each hook is a directory in `hermes-home/hooks/<name>/`:

```text
hermes-home/hooks/task-accepted/
├── HOOK.yaml      # name, events: [agent:start]
└── handler.py
hermes-home/hooks/task-stopped/
├── HOOK.yaml      # name, events: [agent:end]
└── handler.py
```

Identity is **baked in at factory generation time** (the same step that writes
each agent's `SOUL.md`): a small `agent_id` + `team_id` constant in the
handler, or read from `OFFICE_AGENT_ID` / `OFFICE_TEAM_ID` env. The handler
imports the stdlib-only bus client (already mounted at `/opt/office-lib`) and
calls `publish_event()`:

```python
# task-accepted/handler.py (sketch)
import os, sys
sys.path.insert(0, "/opt/office-lib")
from bus.client import BusClient, make_envelope, publish_event

AGENT_ID = os.environ.get("OFFICE_AGENT_ID", "unknown")
TEAM_ID  = os.environ.get("OFFICE_TEAM_ID", "")

def handle(event_type, context):
    env = make_envelope(
        actor=AGENT_ID, action="task.started", target=AGENT_ID,
        team=TEAM_ID or None,
        payload={
            "summary": f"{AGENT_ID} accepted a task",
            "session_id": context.get("session_id"),
            "message": context.get("message", "")[:500],
            "task_ref": _extract_refs(context.get("message", "")),
        },
    )
    publish_event(BusClient(), env)
```

`task-stopped` is identical but publishes `task.finished` and adds
`response` + a best-effort `status` (done/blocked) guessed from the response
text (keyword scan: "blocked", "need ", "question", "token", "permission"…).

### Honest limit: structured task metadata is best-effort at the hook level

`agent:start` gives us `message` (500 chars), not a structured
`{from, pr, issue, linear}`. So `task_ref` is **regex-extracted best-effort**
(PR `#123`, `ISSUE-42`, `DEV-123`, URLs). This is a feature, not a bug: the
controller explicitly **flags tasks whose refs are empty** — that is how we
see "задачи без этих штук". The *authoritative* `task_ref` comes from the
agent's own stop-sync (§4), where the LLM knows the task and writes it
explicitly.

## 4. Stop-sync convention (rich layer)

The hooks answer *"did the agent start / stop?"* deterministically. They cannot
answer *"why did it stop?"* reliably. That is the agent's job, and it is the
one part that can fail — which is exactly the failure mode we are fixing.

Add to `crew/OFFICE-STANDARD.md` (and each SOUL): **before stopping, an agent
SHALL publish exactly one terminal event**:

- `task.finished` with `payload.status = "done"` — work complete, or
- `task.blocked` with `payload.reason` + `payload.kind ∈ {blocker, question}`
  — cannot proceed; this **is** the escalation to the Scrum Master.

The two layers compose into a truth table the controller can act on:

| Hook start | Hook stop | Sync event | Controller verdict |
|-----------|-----------|------------|--------------------|
| ✅ | ✅ | done/blocked | normal; record status |
| ✅ | ✅ | *missing* | **smell** — stopped without syncing (chain-break candidate) |
| ✅ | ❌ | — | **stuck/crashed** — stale heartbeat → manual check |
| ❌ | ✅ | — | out-of-band work (no start seen) — log, don't panic |

## 5. Stale-heartbeat check (the "manual check")

`agent:start` without a matching `agent:end` within `STALL_TIMEOUT`
(default 30m) means the agent is stuck or dead. The Scrum Master controller:

1. sees `state: working` with `last_at` older than the timeout,
2. pings the agent via its door/bus ("are you alive? status?") — this is the
   "вручную проверяет, работает ли агент",
3. if no reply within a short window → publishes `task.stale` and escalates
   (restart via `agent.wake`, or surface to human).

This closes the one gap the hooks cannot: a hard death that fires neither
`agent:end` nor the sync.

## 6. The board (`board.json`)

The Scrum Master's registry. Materialised by the single writer; gitignored
(like `logs/events.jsonl`).

```json
{
  "generated_at": "2026-08-29T20:00:00Z",
  "agents": {
    "dev-1/developer": {
      "team": "dev-1",
      "state": "working" | "stopped",
      "status": "done" | "blocked" | null,
      "reason": "need GH token for org X" | null,
      "last_event": "task.started" | "task.finished" | "task.blocked",
      "last_at": "ISO-8601",
      "session_id": "…",
      "task_ref": { "from": "tech-pm", "pr": null, "issue": "42", "linear": "DEV-123" }
    }
  },
  "events": [
    { "ts": "…", "agent": "dev-1/developer", "event": "task.finished",
      "status": "done", "summary": "…" }
  ]
}
```

**Size:** the `agents` map is ~one entry per agent (16 today). The `events`
array is a rolling window capped at **1000 entries** (configurable), oldest
dropped — plenty for a "свежая сводка", and bounded so the file stays small
and fast to read. This directly answers the "1000 строк хватит?" question:
yes, with room to spare.

The writer also exposes the board via a tiny CLI for humans and the Scrum
Master: `python3 crew/board.py` (or `crew/office-log.py --board`).

## 7. Scrum Master controller (the LLM's job)

A cron job on the scrum-master agent (every N minutes) that runs the
controller skill. It is **deterministic read + LLM judgement**, and it never
writes the board itself (only the board writer writes; the controller may only
*publish* actions like `agent.wake` or `task.stale`).

Its sweep:

1. Read `board.json`.
2. Flag: stale `working` (§5), `blocked` awaiting reply, missing `task_ref`,
   `stopped` without sync.
3. Act: ping stuck agents, resolve/route blockers (self / architect /
   super-devops / human), record `override.recorded` where it intervenes.

This keeps the Scrum Master a *controller* (observe → decide → escalate), not
a second source of truth.

## 8. Event naming (no collision)

`agent.started` / `agent.stopped` already mean **container** lifecycle
(factory-control). Do not overload them. Work-activity uses:

| Event | Source | Meaning |
|-------|--------|---------|
| `task.started`  | hook 1 | agent accepted a unit of work |
| `task.finished` | hook 2 / sync | agent stopped; `status` ∈ {done, blocked, unknown} |
| `task.blocked`  | sync (escalation) | blocked; `reason` + `kind` ∈ {blocker, question} |
| `task.stale`    | controller | no heartbeat; stuck or dead |

`task.started` / `task.finished` / `task.stale` already exist in
`bus/action-schema.json`; `task.blocked` is new.

## 9. Deployment shape

- `scrum-board` compose service: always-on, `restart: unless-stopped`, runs
  `office/scrum/board.py`, mounts the office repo + a shared data dir (same
  mount as the Scrum Master's `/opt/data` so the agent reads `board.json`
  directly).
- Hooks are dropped into every agent home by the factory template (office
  agents + `instances/*/home/*`), with `OFFICE_AGENT_ID` / `OFFICE_TEAM_ID`
  set in each agent's environment.
- Controller cron + skill live in `agents/scrum-master/`.

## 10. Risks / open questions

- **`agent:end` coverage on crash** — mitigated by §5 stale heartbeat, but the
  exact STALL_TIMEOUT needs tuning (30m vs idle 40m interplay with
  factory-control's reaper: a "working" agent must never be reaped while its
  task is alive).
- **Message truncation (500 chars)** — enough for refs and summaries; the
  authoritative refs come from the sync event, not the hook.
- **Where `board.json` physically lives** — shared `/opt/data` mount vs a new
  volume. Decide at implementation; both are fine.
- **Board-writer as its own service vs folded into factory-control** — prefer
  a separate `scrum-board` service (separation: container lifecycle vs work
  activity), but this is a deployment detail.

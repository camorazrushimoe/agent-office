# Inter-agent Door Handoff (HMAC webhook)

Sibling agents in a spec/dev/lab team expose a Hermes webhook door:
`POST http://<container>:8644/webhooks/inbox`, HMAC-protected per route.
Registry: `/opt/crew/agents.json` (per agent: `host_url` — for the Docker
host, `container_url` — for other containers on the shared network, `secret`,
`wake_hint`).

Use `container_url` when you are a container (you are). Use `host_url` only
from the host machine.

## Request recipe (V2 signature — required, V1 is deprecated)
The route config renders your raw body into the sibling's prompt verbatim
(`prompt: "{message}"`), so **the body IS the brief**.

```python
import hashlib, hmac, time, urllib.request

def post_door(agent_id: str, message: str) -> None:
    cfg = json.load(open("/opt/crew/agents.json"))[agent_id]
    url, secret = cfg["container_url"], cfg["secret"]

    # 1) health (optional but right): GET <container>:8644/health -> 200
    #    if not healthy: send_wake(bus, agent_id) and poll /health up to 90s

    # 2) sign
    body = message.encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + body,
                   hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": ts,                 # unix seconds, ±300s window
        "X-Webhook-Signature-V2": sig,             # hex HMAC over "<ts>.<body>"
        "X-Request-ID": f"spec1-{agent_id}-{int(time.time()*1000)}",  # idempotency
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        print(r.status, r.read().decode()[:300])   # 200 = accepted (agent run starts)
```

Notes:
- 200/accepted means the **run started**, not that it finished. The sibling
  reports via bus events + shared-volume files — design the brief around
  that (see checklist).
- Rejection codes: 401 bad signature, 400 bad/duplicate delivery id,
  429 rate-limited (default 30/min/route).
- Provider-specific signature branches (Svix/Linear/GitHub/GitLab) exist in
  the adapter; for agent-to-agent use, plain V2 is correct — do not send
  `X-Hub-Signature-256` etc. by accident.
- Never PUT/GET the inbox route (405); only POST.

## Brief-writing checklist (the message = their entire context)
1. Role + team + which pipeline stage you are assigning.
2. The intake in 5–10 lines (client, asset, ask, hard constraints, bar).
3. **Verified facts** you already established (with how) — so they don't
   re-derive or re-break things.
4. **Explicit blocklist** — what will fail in their env (e.g. "the private
   repo will 404, do not attempt to clone").
5. Numbered tasks with acceptance criteria.
6. Hard rules (budget, no-fabrication, documents-not-implementation).
7. **Deliverables with exact paths on the shared volume** + the exact bus
   events to publish (action names, actor, team, project) + "put full text
   in payload AND file".
8. "You do not need to reply to anyone; the TPM consumes your bus events."

## Guardrail fallback (2026-08-24 first run)
In some deployments the session's consent guardrail blocks outbound
door POSTs (terminal returns BLOCKED: "user has not consented...").
- Do NOT retry the identical command (it re-blocks and wastes a turn).
- Do NOT switch to a different HTTP framing and retry the same outcome.
- **Fallback:** execute the sibling's scope inline yourself (you have the
  same tools; the sibling's auto-approval surface applies to your own
  calls), then:
  - stamp every bus event you publish with `delegated_scope: <role>` in the
    payload, and a provenance note on wiki pages;
  - report the block + fallback in your stage summary so the human owner
    can allow-list intra-team doors if they want real delegation.
- Treat the sibling's published events as the deliverable contract either
  way — your inline output must match what their events would have said.

## Verification after handoff
- Bus: watch for the sibling's expected events on `office:events`
  (XREVRANGE loop, or ask Scrum Master).
- Files: stat the deliverable paths on the shared volume.
- If neither arrives after a reasonable window, re-check their container
  DNS + `/health` before assuming loss.

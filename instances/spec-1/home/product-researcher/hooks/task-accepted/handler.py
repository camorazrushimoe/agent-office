"""task-accepted — thin gateway hook handler (no LLM).

Copied by the factory into every agent's hermes-home/hooks/task-accepted/.
Shared logic lives in /opt/office-lib/activity.py (office repo mount).

The import is wrapped so a missing /opt/office-lib mount degrades to a no-op
instead of raising during hook loading — the hook SHALL NOT break the agent's
turn either way.
"""
import sys

sys.path.insert(0, "/opt/office-lib")

try:
    from activity import on_start  # noqa: E402
except ImportError:  # office lib not mounted -> nothing to do
    on_start = None  # type: ignore[assignment]


def handle(event_type: str, context: dict) -> None:
    if on_start is not None:
        on_start(context)

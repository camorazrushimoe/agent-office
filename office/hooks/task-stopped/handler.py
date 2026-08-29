"""task-stopped — thin gateway hook handler (no LLM).

Copied by the factory into every agent's hermes-home/hooks/task-stopped/.
Shared logic lives in /opt/office-lib/activity.py (office repo mount).
"""
import sys

sys.path.insert(0, "/opt/office-lib")

from activity import on_stop  # noqa: E402


def handle(event_type: str, context: dict) -> None:
    on_stop(context)

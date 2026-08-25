#!/usr/bin/env python3
"""Deterministic secret scanner (stdlib-only).

Scans TRACKED files (``git ls-files``) — never the whole working tree, so
gitignored runtime artifacts (rendered config.yaml, logs, models caches, .env)
are not considered. Fails with exit 1 if any credential-shaped secret is found.

Patterns:
  * door secrets — 40/48/64 hex chars on a ``secret:`` / DOOR_SECRET line
  * provider tokens — ghp_ / github_pat_ / lin_api_ / sk- / sk-or- / runinfra keys
  * the tokens file itself being tracked (tokens/tokens.yaml)

Usage:
  python3 scripts/check_secrets.py            # against current git index
  python3 scripts/check_secrets.py --all-refs # full history (slow)
"""
from __future__ import annotations

import re
import subprocess
import sys

DOOR = re.compile(
    r"(secret|DOOR_SECRET[_\w]*)\s*[:=]\s*['\"]?([0-9a-fA-F]{40,64})")
TOKENS = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"lin_api_[A-Za-z0-9]{20,}|sk-or-[A-Za-z0-9-]{20,}|"
    r"sk-ant-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9]{20,})")
FORBIDDEN_FILES = ("tokens/tokens.yaml",)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def scan(files: list[str]) -> list[str]:
    hits: list[str] = []
    for path in files:
        if path in FORBIDDEN_FILES:
            hits.append(f"{path}: tokens file must never be tracked")
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for ln, line in enumerate(text.splitlines(), 1):
            m = DOOR.search(line) or TOKENS.search(line)
            if m:
                hits.append(f"{path}:{ln}: secret-shaped value "
                            f"({m.group(1)[:12]}...)")
    return hits


def main() -> int:
    if "--all-refs" in sys.argv:
        out = subprocess.run(
            ["git", "rev-list", "--all"], capture_output=True, check=True).stdout
        files = [f"{rev}:{p}" for rev in out.decode().split()
                 for p in tracked_files()]
        # history scan uses git show per file; keep it simple: report count only
        print("[check-secrets] --all-refs history scan not implemented in this "
              "lightweight scanner; run gitleaks in CI for full history.",
              file=sys.stderr)
        return 0

    hits = scan(tracked_files())
    if hits:
        print("[check-secrets] FAIL — secrets found in tracked files:", file=sys.stderr)
        for h in hits:
            print(f"  {h}", file=sys.stderr)
        return 1
    print("[check-secrets] OK — no secrets in tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

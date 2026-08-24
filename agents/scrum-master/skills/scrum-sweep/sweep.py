#!/usr/bin/env python3
"""Scrum Master — GitHub sweep.

Collects the org's repos, open issues, open PRs and recent activity (last N
days) so the Scrum Master can see what's active and triage work.

Usage:
  GITHUB_TOKEN=<token> python3 sweep.py            # readable summary
  GITHUB_TOKEN=<token> python3 sweep.py --json     # machine-readable
  GITHUB_TOKEN=<token> python3 sweep.py --days 14  # wider window

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

ORG = "camorazrushimoe"


def gh(path: str, token: str):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def time_ago(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "—"
    secs = max(0, (now - dt).total_seconds())
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def collect(token: str, org: str, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    now = datetime.now(timezone.utc)
    repos = [r for r in gh(f"/users/{org}/repos?per_page=100&type=owner", token) if not r.get("fork")]
    result = []
    for r in repos:
        name = r["name"]
        pushed_dt = parse_dt(r.get("pushed_at"))
        active = bool(pushed_dt and pushed_dt >= cutoff)
        try:
            items = gh(f"/repos/{org}/{name}/issues?state=open&per_page=50", token)
        except urllib.error.HTTPError:
            items = []
        issues = [i for i in items if "pull_request" not in i]
        prs = [i for i in items if "pull_request" in i]
        result.append({
            "repo": name,
            "active": active,
            "pushed_at": r.get("pushed_at"),
            "open_issues": len(issues),
            "open_prs": len(prs),
            "issues": [
                {
                    "number": i["number"],
                    "title": i["title"],
                    "labels": [l["name"] for l in i.get("labels", [])],
                    "created_at": i.get("created_at"),
                    "updated_at": i.get("updated_at"),
                }
                for i in issues
            ],
        })
    result.sort(key=lambda x: (not x["active"], -x["open_issues"], -x["open_prs"]))
    return result


def render(data: list[dict], days: int) -> str:
    now = datetime.now(timezone.utc)
    lines = [f"🧹 **GitHub sweep** — {now.strftime('%d %b %H:%M UTC')} (last {days}d)", ""]
    active = [d for d in data if d["active"]]
    quiet = [d for d in data if not d["active"] and (d["open_issues"] or d["open_prs"])]
    silent = [d for d in data if not d["active"] and not d["open_issues"] and not d["open_prs"]]

    lines.append(f"🟢 **Active** ({len(active)})")
    for d in active:
        lines.append(
            f"▸ `{d['repo']}` — {d['open_issues']} issues, {d['open_prs']} PRs · pushed {time_ago(parse_dt(d['pushed_at']), now)}"
        )
        for i in d["issues"]:
            labs = f" [`{'`,`'.join(i['labels'])}`]" if i["labels"] else ""
            lines.append(f"    #{i['number']} {i['title'][:70]}{labs}")
    if active:
        lines.append("")

    lines.append(f"🟡 **Quiet but open** ({len(quiet)})")
    for d in quiet:
        lines.append(f"▸ `{d['repo']}` — {d['open_issues']} issues, {d['open_prs']} PRs")
    if quiet:
        lines.append("")

    lines.append(f"⚪ **Silent** ({len(silent)}): " + ", ".join(f"`{d['repo']}`" for d in silent))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--org", default=ORG)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        sys.exit("GITHUB_TOKEN not set in env")

    data = collect(token, args.org, args.days)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render(data, args.days))


if __name__ == "__main__":
    main()

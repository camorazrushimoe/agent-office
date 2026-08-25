#!/usr/bin/env python3
"""Scrum Master — GitHub sweep.

Collects the org's repos, open issues, open PRs and recent activity (last N
days) so the Scrum Master can see what's active and triage work.

Usage:
  GITHUB_TOKEN=<token> python3 sweep.py            # readable summary
  GITHUB_TOKEN=<token> python3 sweep.py --json     # machine-readable
  GITHUB_TOKEN=<token> python3 sweep.py --days 14  # wider window

Stdlib only. Handles rate-limit (403/429) with backoff, follows pagination
(Link header), and never lets one repo's failure kill the whole sweep.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

ORG = "camorazrushimoe"
API = "https://api.github.com"


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    v = e.headers.get("Retry-After") if e.headers else None
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def gh_all(url: str, token: str, retries: int = 4):
    """GET with rate-limit backoff + Link-header pagination. Returns a list."""
    items: list = []
    while url:
        for attempt in range(retries):
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    remaining = r.headers.get("X-RateLimit-Remaining")
                    if remaining is not None and remaining.isdigit() and int(remaining) < 10:
                        print(f"[warn] GitHub rate limit low: {remaining} remaining", file=sys.stderr)
                    data = json.load(r)
                    link = r.headers.get("Link", "")
                if isinstance(data, list):
                    items.extend(data)
                else:
                    items.append(data)
                    return items
                nxt = None
                for part in link.split(","):
                    if 'rel="next"' in part:
                        m = re.search(r"<([^>]+)>", part)
                        nxt = m.group(1) if m else None
                url = nxt if nxt else ""
                break  # success, move to next page
            except urllib.error.HTTPError as e:
                if e.code in (403, 429) and attempt < retries - 1:
                    wait = _retry_after(e) or (2 ** attempt)
                    print(f"[warn] rate limited ({e.code}), retrying in {wait:.0f}s", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise
        else:
            raise RuntimeError(f"rate limit exhausted for {url}")
    return items


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

    try:
        repos = gh_all(f"{API}/users/{org}/repos?per_page=100&type=owner", token)
    except Exception as e:
        print(f"[error] repo list failed: {e}", file=sys.stderr)
        sys.exit(1)

    result = []
    for r in repos:
        if r.get("fork"):
            continue
        name = r["name"]
        pushed_dt = parse_dt(r.get("pushed_at"))
        active = bool(pushed_dt and pushed_dt >= cutoff)

        try:
            items = gh_all(f"{API}/repos/{org}/{name}/issues?state=open&per_page=50", token)
        except Exception as e:
            print(f"[warn] issues for {name} failed ({e}); skipping", file=sys.stderr)
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


def resolve_token() -> str:
    """Find a GitHub token, tolerating Hermes' subprocess hardening.

    Hermes strips GITHUB_TOKEN / GH_TOKEN from tool subprocess environments
    (tools/environments/local.py::_ALWAYS_STRIP_KEYS), so an agent running
    this script can never inherit it — the env var only works when a human
    runs the script on the host. Inside a factory container the token comes
    from the single source of truth mounted at $TOKENS_FILE.
    """
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(var, "").strip()
        if val:
            return val

    tokens_file = os.environ.get("TOKENS_FILE", "/opt/tokens/tokens.yaml")
    if not os.path.isfile(tokens_file):
        return ""
    for lib in ("/opt/office-lib", os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "..", "..", "..", "..", "office")):
        lib = os.path.abspath(lib)
        if os.path.isdir(lib) and lib not in sys.path:
            sys.path.insert(0, lib)
    try:
        from credentials import load_tokens  # noqa: PLC0415
        return ((load_tokens(tokens_file).get("github") or {})
                .get("token") or "").strip()
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--org", default=ORG)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    token = resolve_token()
    if not token:
        sys.exit("No GitHub token: set GITHUB_TOKEN, or make sure "
                 "$TOKENS_FILE (default /opt/tokens/tokens.yaml) has "
                 "github.token and /opt/office-lib is mounted.")

    data = collect(token, args.org, args.days)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render(data, args.days))


if __name__ == "__main__":
    main()

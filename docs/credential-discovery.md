# Credential Discovery Standard (GITHUB_TOKEN & friends)

## Problem (observed 2025-08-25, twice)

Agents look for `GITHUB_TOKEN` in **config files** (`.env`, `.env.bak`,
`config.yaml`) where it is stored only as a commented-out placeholder. The
real token is injected into the container **process environment** by compose
(`environment: - GITHUB_TOKEN=${GITHUB_TOKEN:-}`) and is always available via
`os.environ` / `printenv`.

This cost the spec-1 TPM a misdiagnosis ("repo access blocked") and the
scrum-master most of a sweep session (token hunt instead of work).

## Rule

When an agent needs a credential (any `*_TOKEN`, `*_KEY`, secret):

1. **Check the process environment FIRST**: `printenv <NAME>` /
   `os.environ[<NAME>]`. Compose-injected credentials live there — not in
   dotfiles.
2. Only then inspect files, and treat **commented lines as absent**
   (`# GITHUB_TOKEN=...` means "not configured here").
3. Never print the full value; verify by length / API response code:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" \
     -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user
   ```
   `200` = valid; `401` = invalid/absent.
4. Shell quoting matters: inside `docker exec … sh -c '…'` use SINGLE quotes
   so the variable expands in the container, or run python and read
   `os.environ`.
5. If the credential is genuinely absent from env AND files → report it to
   the operator as a deployment gap instead of burning turns on archaeology.

## Applies to

All agents, all teams. Add this checklist item to intake/triage routines that
touch external services (GitHub, Linear, VK, …).

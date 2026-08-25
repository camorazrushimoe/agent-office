# Secrets — single source of truth

Agent Office keeps every credential the factory is allowed to use in **one
gitignored file** at the top of the hierarchy: `tokens/tokens.yaml`.

```
tokens/tokens.yaml        <- the ONE file (gitignored, chmod 600)
tokens/tokens.example.yaml <- committed schema reference (no real values)
office/credentials.py     <- stdlib loader + resolver
office/render_config.py   <- container entrypoint (resolve -> render -> exec)
office/manage_tokens.py   <- migrate / generate / derive-agents / check
```

No secret lives in `config.yaml`, `.env`, `docker-compose.yml`, or any tracked
file. The rendered `config.yaml` is a runtime artifact (gitignored) written by
`render_config.py` at container boot.

## How an agent gets its credentials

Every container mounts the tokens file and is given three identity variables:

| Env | Meaning | Office example | Team example |
|-----|---------|----------------|--------------|
| `TOKENS_FILE` | path to tokens.yaml | `/opt/tokens/tokens.yaml` | same |
| `FACTORY_NAME` | factory/template for the LLM key | `office` | `dev-crew` |
| `TEAM_NAME` | running instance (door scope) | *(unset)* | `dev-1` |
| `AGENT_ID` | role | `architect` | `developer` |

`office/render_config.py` then:

1. loads `tokens.yaml`;
2. resolves `CUSTOM_API_KEY`, `GITHUB_TOKEN`, `LINEAR_API_KEY`, `DOOR_SECRET`
   for that identity;
3. substitutes `${...}` placeholders in `config.yaml.template`;
4. `exec`s the Hermes gateway with the enriched environment.

It **fails fast** (exit 2) if the tokens file or a referenced placeholder is
missing — it never boots a gateway with a literal `${DOOR_SECRET}`.

## Scoping rules

* `github.token`, `linear.api_key` — shared, the owner's tokens, identical for
  every agent.
* `llm.factories.<factory>` — one LLM key per factory (`office`, `dev-crew`,
  `lab-crew`, `product-factory`), fallback to `default`.
* `doors.<instance>.<agent>` — one per running instance and role (the
  container↔container HMAC secrets), fallback scope `office`.

## Setup / maintenance

```bash
# one-time: consolidate legacy .env credentials into tokens.yaml
python3 office/manage_tokens.py migrate            # add --dry-run to preview

# fresh deployment: generate random 48-hex door secrets from the example
python3 office/manage_tokens.py generate

# regenerate crew/agents.json (host-side door client) from tokens.yaml
python3 office/manage_tokens.py derive-agents

# verify the file is complete and parses
python3 office/manage_tokens.py check
```

## What to do when a token leaks

1. **Rotate the leaked external token** at the provider (GitHub / Linear /
   RunInfra / OpenRouter).
2. **Rotate door secrets** — they are cheap and can be rotated freely:

   ```bash
   python3 office/manage_tokens.py rotate-doors
   python3 office/manage_tokens.py derive-agents
   ```

   Then update any external agent (your entry-point Hermes) that signs
   requests with the old `scrum-master` door secret.
3. **Rewrite history** so the old values stop showing up in `git log` (this is
   a force-push, do it when the branch is quiet):

   ```bash
   git filter-repo --invert-paths \
     --path-glob 'agents/*/hermes-home/config.yaml' \
     --path-glob 'instances/*/home/*/config.yaml'
   git push --force --all
   ```

4. Confirm the safety net catches the pattern next time:
   `python3 scripts/check_secrets.py`.

## Safety net (why gitignore alone is not enough)

`config.yaml` *was* in `.gitignore` and still leaked — gitignore does not
protect files that are already tracked. Defense in depth:

* `tokens/tokens.yaml` gitignored **and** `chmod 600`.
* `config.yaml` removed from git entirely (only `.template` remains).
* **CI** (optional — requires a token with the `workflow` scope, which the
  deploy token may not have): gitleaks over full history + the same
  deterministic repo gate. Drop this file into `.github/workflows/secret-scan.yml`
  and push with a `workflow`-scoped token to enable it:

  ```yaml
  name: secret-scan
  on: [push, pull_request]
  permissions:
    contents: read
  jobs:
    scan:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
          with:
            fetch-depth: 0
        - name: gitleaks
          uses: gitleaks/gitleaks-action@v2
          env:
            GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"
        - name: repo secret gate
          run: python3 scripts/check_secrets.py
  ```

* **pre-commit** (`.pre-commit-config.yaml`): same gate runs locally before
  every commit.
* Door secrets are **generated**, never hand-typed or copy-pasted.
* `crew/agents.json` is **derived** from `tokens.yaml`, never hand-edited.

## Hardening follow-ups (not part of this change)

* Add `requirepass` + a strong password to the shared Redis bus and thread the
  password through `OFFICE_BUS_URL` (coordinated rollout — every bus client
  must switch at once).
* Bind the Redis host port to `127.0.0.1` if no remote bus consumer exists.
* Reconsider mounting `/var/run/docker.sock` into `staff-engineer`,
  `super-devops`, and `dev-1`'s `devops` — it grants container escape; a
  remote-build proxy is safer.

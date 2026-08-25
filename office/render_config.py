#!/usr/bin/env python3
"""Container entrypoint: resolve credentials -> render config.yaml -> exec gateway.

Replaces the previous per-agent render_config.py. One implementation serves
both Office agents and team agents:

  1. load  $TOKENS_FILE  (default /opt/tokens/tokens.yaml)
  2. resolve this agent's credentials via FACTORY_NAME / TEAM_NAME / AGENT_ID
  3. substitute ${VAR} placeholders in /opt/data/config.yaml.template
  4. exec ``hermes gateway run`` with the enriched environment

Fails fast (exit 2) if the tokens file or a referenced placeholder is missing,
instead of booting a gateway with a broken/literal ``${DOOR_SECRET}``.

Test without booting the gateway:
    AGENT_ID=architect FACTORY_NAME=office \
      python3 office/render_config.py --render-only
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from credentials import CredentialsError, load_tokens, resolve_identity  # noqa: E402

TEMPLATE = "/opt/data/config.yaml.template"
TARGET = "/opt/data/config.yaml"
GATEWAY_ARGV = ["hermes", "gateway", "run"]

_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def render(template: str, target: str) -> int:
    try:
        text = open(template, encoding="utf-8").read()
    except OSError as exc:
        raise CredentialsError(f"cannot read template {template}: {exc}") from exc

    def sub(m: "re.Match") -> str:
        var = m.group(1)
        if var not in os.environ:
            raise CredentialsError(
                f"config.yaml.template references ${{{var}}} but it is not set")
        return os.environ[var]

    rendered = _VAR.sub(sub, text)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(rendered)
    return len(rendered)


def main() -> int:
    render_only = "--render-only" in sys.argv
    tokens_file = os.environ.get("TOKENS_FILE", "/opt/tokens/tokens.yaml")
    factory = os.environ.get("FACTORY_NAME", "office")
    team = os.environ.get("TEAM_NAME", "")
    agent = os.environ.get("AGENT_ID", "")

    if not agent:
        print("[render-config] FATAL: AGENT_ID not set", file=sys.stderr)
        return 2

    try:
        tokens = load_tokens(tokens_file)
        os.environ.update(resolve_identity(
            tokens, factory=factory, team=team, agent=agent))
        n = render(TEMPLATE, TARGET)
    except CredentialsError as exc:
        print(f"[render-config] FATAL: {exc}", file=sys.stderr)
        return 2

    print(f"[render-config] wrote {TARGET} ({n} bytes) "
          f"factory={factory} team={team or 'office'} agent={agent}", flush=True)

    if render_only:
        return 0

    os.execvpe("hermes", GATEWAY_ARGV, os.environ)  # no return


if __name__ == "__main__":
    sys.exit(main())

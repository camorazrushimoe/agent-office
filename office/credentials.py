#!/usr/bin/env python3
"""Single source of truth for Agent Office credentials (stdlib-only).

Reads ``tokens/tokens.yaml`` — the ONE gitignored file at the top of the
hierarchy that holds every token the factory is allowed to use — and resolves
the subset an agent is entitled to, based on its identity.

Identity (from container env):
    FACTORY_NAME  — factory/template the agent belongs to (``office``,
                    ``dev-crew``, ``lab-crew``, ``product-factory``).
    TEAM_NAME     — running instance name (``dev-1``, ``lab-1``, ``spec-1``);
                    empty for Office agents (scope falls back to ``office``).
    AGENT_ID      — role (``architect``, ``developer``, ``research-lead``, ...).

Schema (see tokens/tokens.example.yaml):

    llm:
      base_url: https://api.runinfra.ai/v1
      factories:            # one LLM key per factory
        office: ...
        dev-crew: ...
        lab-crew: ...
        product-factory: ...
    linear:
      api_key: ...          # same for every agent (owner's token)
    github:
      token: ...            # same for every agent (owner's token)
    doors:                  # per-instance, per-agent webhook HMAC secrets
      office:
        architect: ...
      dev-1:
        developer: ...

Scoping rules:
  * shared credentials (github.token, linear.api_key) pass through unchanged;
  * LLM key is looked up by FACTORY_NAME (fallback ``default``);
  * door secret is looked up by TEAM_NAME (fallback ``office``) + AGENT_ID.

The YAML parser is deliberately a tiny, fixed subset (scalars only, 2-space
indent, no lists/quotes) so the loader runs anywhere without PyYAML.
"""
from __future__ import annotations

import os
from pathlib import Path


class CredentialsError(RuntimeError):
    pass


# ---- minimal YAML-subset parser -------------------------------------------
def _strip_comment(line: str) -> str:
    # Values in tokens.yaml never contain " #"; stripping inline comments is safe.
    return line.split("#", 1)[0].rstrip()


def parse_tokens(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]  # root indent -1: never popped
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise CredentialsError("tabs are not allowed in tokens.yaml")
        key, sep, val = line.partition(":")
        if not sep or not key.strip():
            raise CredentialsError(f"expected 'key: value', got: {raw!r}")
        key = key.strip()
        raw_val = val.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if raw_val == "":
            # Structural key (`key:`) opens a nested mapping.
            child: dict = {}
            stack[-1][1][key] = child
            stack.append((indent, child))
            continue
        # Scalar value. Strip one layer of matching quotes so "foo" -> foo
        # and "" -> "" (an explicit empty string, distinct from `key:`).
        if len(raw_val) >= 2 and raw_val[0] == raw_val[-1] \
                and raw_val[0] in "\"'":
            raw_val = raw_val[1:-1]
        stack[-1][1][key] = raw_val
    return root


def load_tokens(path: str | os.PathLike | None = None) -> dict:
    p = Path(path) if path else Path(
        os.environ.get("TOKENS_FILE", "/opt/tokens/tokens.yaml"))
    if not p.is_file():
        raise CredentialsError(f"tokens file not found: {p}")
    return parse_tokens(p.read_text(encoding="utf-8"))


# ---- identity resolution --------------------------------------------------
def _pick(mapping: dict, *names: str) -> str:
    for n in names:
        v = mapping.get(n)
        if v:
            return v
    return ""


def resolve_identity(tokens: dict, *, factory: str = "office",
                     team: str = "", agent: str = "") -> dict:
    """Return the env vars this agent is entitled to (never prints values)."""
    env: dict = {}

    # LLM key — one per factory, fallback to ``default``.
    llm = tokens.get("llm") or {}
    factories = llm.get("factories") or {}
    key = _pick(factories, factory or "office", "default")
    if key:
        # CUSTOM_API_KEY is what config.yaml.template references; set the
        # OpenRouter alias too so the gateway works regardless of provider.
        env["CUSTOM_API_KEY"] = key
        env["OPENROUTER_API_KEY"] = key
    base_url = llm.get("base_url")
    if base_url:
        env["LLM_BASE_URL"] = base_url

    # Shared (owner) credentials — same for every agent.
    linear = (tokens.get("linear") or {}).get("api_key")
    if linear:
        env["LINEAR_API_KEY"] = linear
    github = (tokens.get("github") or {}).get("token")
    if github:
        env["GITHUB_TOKEN"] = github

    # Per-instance, per-agent door secret.
    doors = tokens.get("doors") or {}
    scope = team or "office"
    door = (doors.get(scope) or {}).get(agent)
    if door:
        env["DOOR_SECRET"] = door

    return env

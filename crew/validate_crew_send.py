#!/usr/bin/env python3
"""Deterministic validation for crew/crew-send.py (no LLM, no pytest).

Run:  python3 crew/validate_crew_send.py
Exit: 0 on success, 1 on any failed check.

Covers the wake-on-failure contract (spec: add-door-client-wake-path):
  - wake target derivation: container_url host -> controller-recognized id,
    wake_hint override, team:role -> team-role normalization
  - wake decision: 4xx -> no wake; connection failure / 5xx -> wake
  - health URL derivation from the delivery door URL
  - re-delivery failure after a successful wake -> non-zero (no silent drop)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import urllib.error
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))   # crew
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# crew-send.py has a hyphen in its filename, so it cannot be imported by
# module name; load it explicitly by path.
_spec = importlib.util.spec_from_file_location(
    "crew_send", os.path.join(HERE, "crew-send.py"))
assert _spec and _spec.loader
crew_send = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crew_send)

FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got!r}"
          + ("" if ok else f"  (want {want!r})"))
    if not ok:
        FAILURES.append(name)


def test_wake_target_derivation() -> None:
    # Registry key `developer` in dev-1 -> container_url host dev-1-developer
    # (the exact id/container factory-control registers).
    cfg = {"container_url": "http://dev-1-developer:8644/webhooks/inbox",
           "secret": "s"}
    check("dev-1 developer -> dev-1-developer",
          crew_send.wake_target(cfg), "dev-1-developer")
    check("office architect -> architect",
          crew_send.wake_target(
              {"container_url": "http://architect:8644/webhooks/inbox",
               "secret": "s"}),
          "architect")

    # wake_hint overrides and is normalized team:role -> team-role.
    cfg = {"container_url": "http://wrong-host:8644/webhooks/inbox",
           "wake_hint": "dev-1:developer", "secret": "s"}
    check("wake_hint overrides container_url host",
          crew_send.wake_target(cfg), "dev-1-developer")
    check("wake_hint hyphenated passthrough",
          crew_send.wake_target(
              {"container_url": "http://x:8644/", "wake_hint": "lab-1-evaluation",
               "secret": "s"}),
          "lab-1-evaluation")

    # No container_url host, no hint -> empty (caller must fail loudly).
    check("missing both -> empty target",
          crew_send.wake_target({"secret": "s"}), "")


def test_wake_decision() -> None:
    check("4xx -> no wake",
          crew_send.should_wake(urllib.error.HTTPError(
              "url", 401, "Unauthorized", None, None)), False)
    check("404 -> no wake",
          crew_send.should_wake(urllib.error.HTTPError(
              "url", 404, "Not Found", None, None)), False)
    check("5xx -> wake",
          crew_send.should_wake(urllib.error.HTTPError(
              "url", 503, "Unavailable", None, None)), True)
    check("connection refused -> wake",
          crew_send.should_wake(ConnectionRefusedError()), True)
    check("timeout -> wake",
          crew_send.should_wake(TimeoutError()), True)


def test_health_url() -> None:
    check("container door -> /health",
          crew_send.health_url("http://dev-1-developer:8644/webhooks/inbox"),
          "http://dev-1-developer:8644/health")
    check("host door -> /health",
          crew_send.health_url("http://127.0.0.1:8661/webhooks/inbox"),
          "http://127.0.0.1:8661/health")


def test_redelivery_failure_after_wake() -> None:
    """Wake succeeds (health 200) but the re-delivery POST fails -> non-zero.

    Exercises send()'s wake path with a mocked bus and mocked HTTP: first
    POST raises connection refused, health comes back 200, re-delivery POST
    raises again -> WakeError (never a silent drop)."""
    with tempfile.TemporaryDirectory() as d:
        reg = os.path.join(d, "agents.json")
        with open(reg, "w", encoding="utf-8") as f:
            json.dump({"dev-1-qa": {
                "host_url": "http://127.0.0.1:8662/webhooks/inbox",
                "container_url": "http://dev-1-qa:8644/webhooks/inbox",
                "secret": "s"}}, f)

        calls: list[str] = []
        woken: list[str] = []

        class FakeResp:
            status = 200

            def read(self):
                return b"ok"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=30):
            url = getattr(req, "full_url", req)  # Request obj or plain URL
            calls.append(url)
            # Health probe always answers 200 — the wake succeeds.
            if url.endswith("/health"):
                return FakeResp()
            # Delivery POST: first attempt fails (door down), so does the
            # re-delivery after a successful wake.
            raise ConnectionRefusedError("door lost")

        with mock.patch.object(crew_send, "REGISTRY", reg), \
             mock.patch.object(crew_send.urllib.request, "urlopen",
                               side_effect=fake_urlopen), \
             mock.patch.object(crew_send, "publish_wake",
                               side_effect=lambda t, a: woken.append(t)):
            try:
                crew_send.send("dev-1-qa", "msg", use_container=True)
                got = "NO ERROR"
            except crew_send.WakeError as e:
                got = str(e)

    check("re-delivery failure after wake -> WakeError (non-zero)",
          "re-delivery" in got, True)
    check("wake was published before re-delivery attempt",
          woken, ["dev-1-qa"])


def test_canonical_client_rule() -> None:
    """Composition spec: exactly one door client, no per-instance copies.

    - no instances/*/crew/crew-send.py copies remain (lab-1 removed)
    - every instance compose mounts the canonical file read-only at
      /opt/crew/crew-send.py on every agent service
    """
    import hashlib

    office_root = os.path.abspath(os.path.join(HERE, ".."))
    canonical = os.path.join(HERE, "crew-send.py")
    with open(canonical, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    instances = os.path.join(office_root, "instances")
    copies = []
    for inst in sorted(os.listdir(instances)):
        crew_dir = os.path.join(instances, inst, "crew")
        if not os.path.isdir(crew_dir):
            continue
        for name in sorted(os.listdir(crew_dir)):
            if name == "crew-send.py":
                p = os.path.join(crew_dir, name)
                with open(p, "rb") as f:
                    same = hashlib.sha256(f.read()).hexdigest() == sha
                copies.append(f"{inst}/crew/{name} (sha256 match: {same})")
    check("no per-instance crew-send.py copies remain", copies, [])

    # every agent service in every instance compose mounts the canonical file
    missing_mounts = []
    for inst in sorted(os.listdir(instances)):
        compose = os.path.join(instances, inst, "docker-compose.yml")
        if not os.path.isfile(compose):
            continue
        with open(compose, encoding="utf-8") as f:
            lines = f.read().splitlines()
        # split into service blocks under the top-level `services:` section:
        # a 2-space-indented `  name:` line, followed by 6-space volume mounts.
        # APPROXIMATION: this is a deterministic structural check, not a YAML
        # parser — it relies on the repo's uniform compose indentation and
        # only inspects volume lines; `docker compose config` is the real
        # syntax gate and is run separately at deploy time.
        current = None
        services = {}
        in_services = False
        for ln in lines:
            if not in_services:
                if ln.strip() == "services:":
                    in_services = True
                continue
            if ln.startswith("  ") and not ln.startswith("   ") and ln.rstrip().endswith(":"):
                current = ln.strip().rstrip(":")
                services.setdefault(current, [])
            elif ln.startswith("      - ") and current is not None:
                services[current].append(ln.strip())
        for svc, mounts in services.items():
            if not any("crew-send.py:/opt/crew/crew-send.py:ro" in m for m in mounts):
                missing_mounts.append(f"{inst}/{svc}")
    check("every agent service mounts the canonical client", missing_mounts, [])


def main() -> int:
    test_wake_target_derivation()
    test_wake_decision()
    test_health_url()
    test_redelivery_failure_after_wake()
    test_canonical_client_rule()
    print()
    if FAILURES:
        print(f"FAILURES ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

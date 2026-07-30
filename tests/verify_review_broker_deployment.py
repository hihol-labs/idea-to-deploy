#!/usr/bin/env python3
"""Static and mutation guards for the broker production package."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKS = 0


def check(value: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not value:
        raise AssertionError(label)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    dockerfile = read("services/review_broker/Dockerfile")
    compose = read("services/review_broker/deploy/compose.yaml")
    unit = read(
        "services/review_broker/deploy/systemd/"
        "itd-review-broker.service"
    )
    caddy = read(
        "services/review_broker/deploy/Caddyfile.example"
    )
    requirements = read(
        "services/review_broker/requirements.lock"
    ).splitlines()
    ignore = read(".dockerignore")
    operations = read(
        "services/review_broker/deploy/README.md"
    )
    run_all = read("tests/run-all.sh")

    check(
        bool(
            re.search(
                r"^FROM python:3\.12\.11-slim-bookworm"
                r"@sha256:[0-9a-f]{64}$",
                dockerfile,
                re.MULTILINE,
            )
        ),
        "container base is digest pinned",
    )
    check(
        "USER 65532:65532" in dockerfile
        and "HEALTHCHECK" in dockerfile
        and "COPY . " not in dockerfile,
        "container is unprivileged and copies a bounded context",
    )
    check(
        "OPENAI_API_KEY" not in dockerfile
        and "ARG OPENAI" not in dockerfile,
        "container build has no provider credential channel",
    )
    check(
        requirements == [
            "cryptography==49.0.0",
            "jsonschema==4.25.1",
        ],
        "direct runtime dependencies are exact",
    )
    for marker in (
        "read_only: true",
        "no-new-privileges:true",
        "cap_drop:",
        '"127.0.0.1:8080:8080"',
        "ITD_OPENAI_API_KEY_FILE: /run/secrets/",
        'OPENAI_API_KEY: ""',
        "/run/secrets/openai-service-account-key:ro",
    ):
        check(marker in compose, f"Compose hardening marker: {marker}")
    check(
        "${OPENAI_API_KEY" not in compose
        and "sk-proj-" not in compose,
        "Compose never imports a developer OpenAI environment key",
    )
    check(
        unit.count("LoadCredentialEncrypted=") == 4
        and "User=itd-review" in unit
        and "ProtectSystem=strict" in unit
        and "NoNewPrivileges=true" in unit,
        "systemd path uses encrypted credentials and sandboxing",
    )
    check(
        "max_size 2MB" in caddy
        and "reverse_proxy 127.0.0.1:8080" in caddy,
        "TLS proxy bounds bodies and targets loopback",
    )
    check(
        ignore.startswith("*\n")
        and "**/__pycache__/" in ignore
        and "**/*.pyc" in ignore,
        "Docker context is allowlisted and excludes bytecode",
    )
    check(
        "previously disclosed in chat is ineligible" in operations
        and "candidate code is never checked out" in operations.lower(),
        "operations guide preserves the secret and execution boundaries",
    )
    check(
        "verify_review_broker_deployment" in run_all,
        "deployment oracle is in the cumulative suite",
    )

    print(
        json.dumps(
            {"checks": CHECKS, "status": "PASSED"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

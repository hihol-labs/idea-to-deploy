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


def compose_service_block(text: str, service: str) -> str:
    """Return one exact two-space-indented Compose service mapping."""
    lines = text.splitlines()
    if sum(line == "services:" for line in lines) != 1:
        raise AssertionError("Compose services mapping is not unique")
    marker = f"  {service}:"
    starts = [index for index, line in enumerate(lines) if line == marker]
    if len(starts) != 1:
        raise AssertionError(f"Compose service {service!r} is not unique")
    start = starts[0]
    if not any(line == "services:" for line in lines[:start]):
        raise AssertionError(f"Compose service {service!r} is outside services")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 2:
            end = index
            break
    return "\n".join(lines[start:end])


def parse_compose_service(text: str, service: str) -> dict:
    """Parse the repository's bounded Compose subset and reject duplicates."""
    lines = compose_service_block(text, service).splitlines()
    result: dict[str, object] = {}
    current_key: str | None = None
    for line in lines[1:]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        content = line.strip()
        if indent == 4:
            if ":" not in content:
                raise AssertionError("Compose service entry is malformed")
            key, raw = content.split(":", 1)
            if not key or key in result:
                raise AssertionError("Compose service key is duplicated")
            raw = raw.strip()
            result[key] = raw if raw else None
            current_key = key
            continue
        if indent != 6 or current_key is None:
            raise AssertionError("Compose service nesting is unsupported")
        if content.startswith("- "):
            if result[current_key] is None:
                result[current_key] = []
            if not isinstance(result[current_key], list):
                raise AssertionError("Compose key mixes list and mapping values")
            result[current_key].append(content[2:].strip())
            continue
        if ":" not in content:
            raise AssertionError("Compose nested mapping entry is malformed")
        key, raw = content.split(":", 1)
        if result[current_key] is None:
            result[current_key] = {}
        if not isinstance(result[current_key], dict):
            raise AssertionError("Compose key mixes mapping and scalar values")
        nested = result[current_key]
        if not key or key in nested:
            raise AssertionError("Compose nested key is duplicated")
        nested[key] = raw.strip()
    if any(value is None for value in result.values()):
        raise AssertionError("Compose service contains an empty mapping")
    return result


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
    requirements = read("services/review_broker/requirements.lock")
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
    effective_dockerfile = "\n".join(
        line for line in dockerfile.splitlines()
        if not line.lstrip().startswith("#")
    )
    effective_compose = "\n".join(
        line for line in compose.splitlines()
        if not line.lstrip().startswith("#")
    )
    broker_service = compose_service_block(
        effective_compose, "review-broker"
    )
    parsed_broker_service = parse_compose_service(
        effective_compose, "review-broker"
    )
    check(
        re.search(r"^USER 65532:65532$", effective_dockerfile, re.MULTILINE)
        is not None
        and re.search(r"^HEALTHCHECK\b", effective_dockerfile, re.MULTILINE)
        is not None
        and re.search(r"^COPY\s+\.\s", effective_dockerfile, re.MULTILINE)
        is None,
        "container is unprivileged and copies a bounded context",
    )
    check(
        "OPENAI_API_KEY" not in dockerfile
        and "ARG OPENAI" not in dockerfile,
        "container build has no provider credential channel",
    )
    expected_packages = {
        "attrs": "26.1.0",
        "cffi": "2.1.0",
        "cryptography": "49.0.0",
        "jsonschema": "4.25.1",
        "jsonschema-specifications": "2025.9.1",
        "pycparser": "3.0",
        "referencing": "0.37.0",
        "rpds-py": "2026.6.3",
        "typing-extensions": "4.16.0",
    }
    package_rows = [
        (index, match.group(1), match.group(2))
        for index, line in enumerate(requirements.splitlines())
        if (
            match := re.fullmatch(
                r"([a-z0-9][a-z0-9-]*)==([^ \t\\]+) \\",
                line,
            )
        )
    ]
    check(
        {name: version for _, name, version in package_rows}
        == expected_packages,
        "runtime dependency graph is transitively pinned",
    )
    requirement_lines = requirements.splitlines()
    for position, (start, name, _version) in enumerate(package_rows):
        end = (
            package_rows[position + 1][0]
            if position + 1 < len(package_rows)
            else len(requirement_lines)
        )
        hashes = [
            line.strip().removesuffix(" \\")
            for line in requirement_lines[start + 1:end]
            if line.strip()
        ]
        check(
            bool(hashes)
            and all(
                re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", value)
                for value in hashes
            ),
            f"{name} distributions are SHA-256 bound",
        )
    check(
        "--require-hashes" in effective_dockerfile
        and "--only-binary=:all:" in effective_dockerfile,
        "container installation enforces hashed binary artifacts",
    )
    ambient_provider_name = "".join(("OPENAI_", "API_KEY"))
    expected_broker_service = {
        "build": {
            "context": "../../..",
            "dockerfile": "services/review_broker/Dockerfile",
        },
        "image": "itd-review-broker:local",
        "init": "true",
        "restart": "unless-stopped",
        "read_only": "true",
        "user": '"65532:65532"',
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "pids_limit": "128",
        "mem_limit": "768m",
        "cpus": "1.0",
        "stop_grace_period": "30s",
        "tmpfs": ["/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777"],
        "ports": ['"127.0.0.1:8080:8080"'],
        "environment": {
            "ITD_GITHUB_APP_CLIENT_ID":
                '"${ITD_GITHUB_APP_CLIENT_ID:?set the App client id}"',
            "ITD_GITHUB_APP_PRIVATE_KEY_FILE":
                "/run/secrets/github-app-private-key",
            "ITD_GITHUB_WEBHOOK_SECRET_FILE":
                "/run/secrets/github-webhook-secret",
            "ITD_PROVENANCE_KEYRING_FILE":
                "/run/secrets/provenance-keyring",
            "ITD_FREE_REVIEWER_KEYRING_FILE":
                "/run/secrets/free-reviewer-keyring",
            "ITD_FREE_REVIEW_APP_SIGNING_KEY_FILE":
                "/run/secrets/free-review-app-signing-key",
            "ITD_FREE_REVIEW_APP_KEY_ID":
                '"${ITD_FREE_REVIEW_APP_KEY_ID:?set the App receipt key id}"',
            "ITD_BROKER_DATABASE":
                "/var/lib/itd/review-broker.sqlite3",
            "ITD_BROKER_HOST": "0.0.0.0",
            "ITD_BROKER_PORT": '"8080"',
        },
        "volumes": [
            "./runtime/database:/var/lib/itd",
            (
                "./runtime/secrets/github-app-private-key.pem:"
                "/run/secrets/github-app-private-key:ro"
            ),
            (
                "./runtime/secrets/github-webhook-secret:"
                "/run/secrets/github-webhook-secret:ro"
            ),
            (
                "./runtime/secrets/provenance-keyring.json:"
                "/run/secrets/provenance-keyring:ro"
            ),
            (
                "./runtime/secrets/free-reviewer-keyring.json:"
                "/run/secrets/free-reviewer-keyring:ro"
            ),
            (
                "./runtime/secrets/free-review-app-signing-key:"
                "/run/secrets/free-review-app-signing-key:ro"
            ),
        ],
    }
    check(
        parsed_broker_service == expected_broker_service
        and ambient_provider_name
        not in parsed_broker_service["environment"],
        "effective Compose service is an exact hardening allowlist",
    )
    dangerous_mutations = (
        effective_compose.replace(
            "    read_only: true\n",
            "    read_only: true\n    privileged: true\n",
            1,
        ),
        effective_compose.replace(
            "    volumes:\n",
            "    cap_add:\n      - SYS_ADMIN\n    volumes:\n",
            1,
        ),
        effective_compose.replace(
            "      - ./runtime/database:/var/lib/itd\n",
            (
                "      - ./runtime/database:/var/lib/itd\n"
                "      - /var/run/docker.sock:/var/run/docker.sock\n"
            ),
            1,
        ),
        effective_compose.replace(
            "      ITD_BROKER_PORT: \"8080\"\n",
            (
                "      ITD_BROKER_PORT: \"8080\"\n"
                f"      {ambient_provider_name}: forbidden\n"
            ),
            1,
        ),
    )
    check(
        all(
            parse_compose_service(mutant, "review-broker")
            != expected_broker_service
            for mutant in dangerous_mutations
        ),
        "dangerous Compose service additions must fail the exact allowlist",
    )
    decoy_compose = (
        effective_compose.replace("    read_only: true\n", "", 1)
        + "\n  decoy:\n    read_only: true\n"
    )
    check(
        re.search(
            r"^    read_only: true$",
            compose_service_block(decoy_compose, "review-broker"),
            re.MULTILINE,
        )
        is None,
        "controls in another Compose service cannot satisfy broker checks",
    )
    conflicting_compose = effective_compose.replace(
        "    read_only: true\n",
        "    read_only: true\n    read_only: false\n",
        1,
    )
    try:
        parse_compose_service(conflicting_compose, "review-broker")
    except AssertionError:
        duplicate_rejected = True
    else:
        duplicate_rejected = False
    check(
        duplicate_rejected
        and parsed_broker_service["read_only"] == "true",
        "effective Compose mapping rejects conflicting duplicate keys",
    )
    check(
        re.search(r"^\s+OPENAI_API_KEY:", compose, re.MULTILINE) is None
        and "Environment=OPENAI_API_KEY=" not in unit
        and "sk-proj-" not in compose,
        "deployment never declares an ambient OpenAI credential channel",
    )
    check(
        unit.count("LoadCredentialEncrypted=") == 5
        and "openai-service-account-key" not in unit
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
        "python3 -m venv /opt/itd-review-broker/venv" in operations
        and "--require-hashes" in operations
        and "services/review_broker/requirements.lock" in operations,
        "systemd operations guide creates the locked runtime used by ExecStart",
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

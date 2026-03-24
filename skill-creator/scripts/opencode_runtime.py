"""Helpers for invoking OpenCode and parsing JSON output."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class OpenCodeRuntimeError(RuntimeError):
    """Base error for OpenCode runtime failures."""


class OpenCodeNotFoundError(OpenCodeRuntimeError):
    """Raised when the opencode binary is not available."""


class OpenCodeMalformedOutputError(OpenCodeRuntimeError):
    """Raised when opencode output cannot be parsed as valid JSON."""


def _truncate(text: str, limit: int = 280) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def parse_opencode_json_output(output: str) -> list[dict]:
    """Parse OpenCode output as NDJSON events or a final JSON payload.

    Fail-closed semantics: malformed or unexpected payloads raise
    OpenCodeMalformedOutputError.
    """
    stripped = output.strip()
    if not stripped:
        raise OpenCodeMalformedOutputError("opencode produced empty stdout")

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    parsed_lines: list[dict] = []
    ndjson_ok = True
    for idx, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            ndjson_ok = False
            break
        if not isinstance(event, dict):
            raise OpenCodeMalformedOutputError(
                f"opencode NDJSON line {idx} is not an object"
            )
        parsed_lines.append(event)

    if ndjson_ok and parsed_lines:
        return parsed_lines

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        snippet = _truncate(stripped)
        raise OpenCodeMalformedOutputError(
            "opencode output is not valid JSON (expected NDJSON events or JSON payload); "
            f"snippet={snippet!r}"
        ) from exc

    if isinstance(payload, dict):
        return [payload]

    if isinstance(payload, list):
        if not payload:
            raise OpenCodeMalformedOutputError("opencode returned an empty JSON array")
        if not all(isinstance(item, dict) for item in payload):
            raise OpenCodeMalformedOutputError(
                "opencode JSON array must contain only objects"
            )
        return payload

    raise OpenCodeMalformedOutputError(
        "opencode JSON payload must be an object or array of objects"
    )


def run_opencode_json(
    message: str,
    timeout_seconds: int,
    workdir: Path,
    model: str | None = None,
) -> list[dict]:
    """Run OpenCode in JSON mode and return parsed event objects."""
    text = run_opencode_text(
        message=message,
        timeout_seconds=timeout_seconds,
        workdir=workdir,
        model=model,
        output_format="json",
    )

    return parse_opencode_json_output(text)


def run_opencode_text(
    message: str,
    timeout_seconds: int,
    workdir: Path,
    model: str | None = None,
    output_format: str | None = None,
) -> str:
    """Run OpenCode and return stdout text.

    Pass output_format (for example "json") when a specific output
    representation is required.
    """
    cmd = ["opencode", "run", message, "--dir", str(workdir)]
    if output_format:
        cmd.extend(["--format", output_format])
    if model:
        cmd.extend(["--model", model])

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OpenCodeNotFoundError(
            "opencode CLI not found. Install it and ensure `opencode` is on PATH."
        ) from exc

    if result.returncode != 0:
        stderr = _truncate(result.stderr)
        raise OpenCodeRuntimeError(
            f"opencode run failed with exit code {result.returncode}. stderr={stderr!r}"
        )

    return result.stdout

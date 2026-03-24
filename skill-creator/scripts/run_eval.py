#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes OpenCode to trigger (use the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.opencode_runtime import (
    OpenCodeMalformedOutputError,
    OpenCodeNotFoundError,
    OpenCodeRuntimeError,
    run_opencode_json,
)
from scripts.utils import parse_skill_md


def _extract_tool_calls(event: dict) -> tuple[list[tuple[str, dict]], bool]:
    """Extract tool calls from known OpenCode event shapes.

    Returns (calls, recognized_shape) where calls are (tool_name, tool_input)
    pairs. recognized_shape=True means the event object matched at least one
    known envelope, even if no tool call was present.
    """
    calls: list[tuple[str, dict]] = []
    recognized = False

    if not isinstance(event, dict):
        return calls, recognized

    if any(key in event for key in ("type", "events", "event", "message", "part")):
        recognized = True

    wrapped_event = event.get("event")
    if isinstance(wrapped_event, dict):
        wrapped_calls, wrapped_recognized = _extract_tool_calls(wrapped_event)
        calls.extend(wrapped_calls)
        recognized = recognized or wrapped_recognized

    # Shape: {"type":"tool_use", "part":{"type":"tool","tool":"skill","state":{"input":{...}}}}
    if event.get("type") == "tool_use":
        part = event.get("part")
        if isinstance(part, dict) and part.get("type") == "tool":
            tool_name = part.get("tool")
            state = part.get("state")
            if isinstance(tool_name, str) and isinstance(state, dict):
                tool_input = state.get("input")
                if isinstance(tool_input, dict):
                    calls.append((tool_name, tool_input))

        # Alternate shape: {"type":"tool_use", "name":"skill", "input":{...}}
        tool_name = event.get("name")
        tool_input = event.get("input")
        if isinstance(tool_name, str) and isinstance(tool_input, dict):
            calls.append((tool_name, tool_input))

    # Shape: {"message":{"content":[{"type":"tool_use","name":"skill","input":{...}}]}}
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "tool_use":
                    continue
                tool_name = item.get("name")
                tool_input = item.get("input")
                if isinstance(tool_name, str) and isinstance(tool_input, dict):
                    calls.append((tool_name, tool_input))

    return calls, recognized


def _iter_event_objects(payloads: list[dict]):
    for payload in payloads:
        yield payload
        nested_events = payload.get("events")
        if isinstance(nested_events, list):
            for event in nested_events:
                if isinstance(event, dict):
                    yield event


def _safe_skill_name(raw_name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw_name).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "eval-skill"


def _write_temp_skill(run_dir: Path, skill_name: str, skill_description: str) -> tuple[str, Path]:
    unique_id = uuid.uuid4().hex[:8]
    temp_skill_name = f"{_safe_skill_name(skill_name)}-eval-{unique_id}"
    temp_skill_dir = run_dir / ".opencode" / "skill" / temp_skill_name
    temp_skill_file = temp_skill_dir / "SKILL.md"
    temp_skill_dir.mkdir(parents=True, exist_ok=True)
    indented_desc = "\n  ".join(skill_description.split("\n"))
    temp_skill_file.write_text(
        (
            "---\n"
            f"name: {temp_skill_name}\n"
            "description: |\n"
            f"  {indented_desc}\n"
            "---\n\n"
            f"# {skill_name}\n"
        ),
        encoding="utf-8",
    )
    return temp_skill_name, temp_skill_file


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    run_dir: str,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the target skill was triggered."""
    run_dir_path = Path(run_dir)
    temp_skill_name, temp_skill_file = _write_temp_skill(run_dir_path, skill_name, skill_description)

    try:
        events = run_opencode_json(
            message=query,
            timeout_seconds=timeout,
            workdir=run_dir_path,
            model=model,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenCodeRuntimeError(
            f"OpenCode timed out after {timeout}s for query {query[:80]!r}"
        ) from exc
    except OpenCodeNotFoundError:
        raise
    except OpenCodeMalformedOutputError as exc:
        raise OpenCodeMalformedOutputError(
            f"Malformed JSON output for query {query[:80]!r}: {exc}"
        ) from exc
    except OpenCodeRuntimeError as exc:
        raise OpenCodeRuntimeError(
            f"OpenCode runtime failure for query {query[:80]!r}: {exc}"
        ) from exc
    finally:
        if temp_skill_file.exists():
            temp_skill_file.unlink()
            try:
                temp_skill_file.parent.rmdir()
            except OSError:
                pass

    recognized_shape = False
    for event in _iter_event_objects(events):
        calls, recognized = _extract_tool_calls(event)
        recognized_shape = recognized_shape or recognized
        for tool_name, tool_input in calls:
            requested_skill = tool_input.get("name")
            if tool_name == "skill" and isinstance(requested_skill, str) and requested_skill.strip() == temp_skill_name:
                return True

    if not recognized_shape:
        raise OpenCodeMalformedOutputError(
            "OpenCode output did not contain any recognizable event envelopes"
        )

    return False


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    run_dir: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []
    query_triggers: dict[int, list[bool]] = {}
    eval_items: dict[int, dict] = {}
    errors: list[str] = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for idx, item in enumerate(eval_set):
            query_triggers[idx] = []
            eval_items[idx] = item
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(run_dir),
                    model,
                )
                future_to_info[future] = (idx, run_idx)

        for future in as_completed(future_to_info):
            idx, run_idx = future_to_info[future]
            try:
                query_triggers[idx].append(future.result())
            except Exception as e:
                query = eval_items[idx]["query"]
                errors.append(
                    f"eval_index={idx} run={run_idx} query={query[:60]!r} error={type(e).__name__}: {e}"
                )

    if errors:
        sample = "; ".join(errors[:3])
        raise OpenCodeRuntimeError(
            f"{len(errors)} eval run(s) failed. sample={sample}"
        )

    for idx in range(len(eval_set)):
        item = eval_items[idx]
        query = item["query"]
        triggers = query_triggers[idx]
        if len(triggers) != runs_per_query:
            raise OpenCodeRuntimeError(
                "Incomplete run results for "
                f"eval_index={idx}: expected {runs_per_query}, got {len(triggers)}"
            )
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for an OpenCode skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model to use for opencode run (default: configured model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    if args.num_workers < 1:
        print("Error: --num-workers must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.runs_per_query < 1:
        print("Error: --runs-per-query must be >= 1", file=sys.stderr)
        sys.exit(1)
    if not 0.0 <= args.trigger_threshold <= 1.0:
        print("Error: --trigger-threshold must be between 0 and 1", file=sys.stderr)
        sys.exit(1)
    if args.timeout < 1:
        print("Error: --timeout must be >= 1 second", file=sys.stderr)
        sys.exit(1)

    if shutil.which("opencode") is None:
        print(
            "Error: `opencode` CLI not found on PATH. Install OpenCode and retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _ = parse_skill_md(skill_path)
    description = args.description or original_description
    run_dir = skill_path

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        run_dir=run_dir,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

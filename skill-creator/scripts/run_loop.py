#!/usr/bin/env python3
"""Run the eval + improve loop until all pass or max iterations reached.

Combines run_eval.py and improve_description.py in a loop, tracking history
and returning the best description found. Supports train/test split to prevent
overfitting.
"""

import argparse
import json
import random
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_report import generate_html
from scripts.improve_description import improve_description
from scripts.run_eval import run_eval
from scripts.utils import parse_skill_md


def split_eval_set(eval_set: list[dict], holdout: float, seed: int = 42) -> tuple[list[int], list[int]]:
    """Return train/test indices using a deterministic stratified split."""
    rng = random.Random(seed)

    # Separate by should_trigger while preserving original index identity.
    trigger = [idx for idx, item in enumerate(eval_set) if item["should_trigger"]]
    no_trigger = [idx for idx, item in enumerate(eval_set) if not item["should_trigger"]]

    # Shuffle each group
    rng.shuffle(trigger)
    rng.shuffle(no_trigger)

    def test_count(group_size: int) -> int:
        if group_size <= 1:
            return 0
        count = int(group_size * holdout)
        if holdout > 0 and count == 0:
            count = 1
        return min(group_size - 1, count)

    # Calculate split points
    n_trigger_test = test_count(len(trigger))
    n_no_trigger_test = test_count(len(no_trigger))

    # Split
    test_indices = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_indices = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]

    return train_indices, test_indices


def select_best_iteration(history: list[dict]) -> dict:
    """Select best iteration using train-only metrics.

    Holdout/test scores are never used for winner selection to avoid repeated
    peeking at holdout performance.
    """
    if not history:
        raise ValueError("history cannot be empty")

    def train_selection_key(item: dict) -> tuple[float, int]:
        train_total = item.get("train_total", 0)
        train_passed = item.get("train_passed", 0)
        rate = (train_passed / train_total) if train_total else 0.0
        # Earlier iteration wins ties to keep selection deterministic.
        return (rate, -item.get("iteration", 0))

    return max(history, key=train_selection_key)


def run_loop(
    eval_set: list[dict],
    skill_path: Path,
    description_override: str | None,
    num_workers: int,
    timeout: int,
    max_iterations: int,
    runs_per_query: int,
    trigger_threshold: float,
    holdout: float,
    split_seed: int,
    model: str,
    verbose: bool,
    live_report_path: Path | None = None,
    log_dir: Path | None = None,
) -> dict:
    """Run the eval + improvement loop."""
    if not 0.0 <= holdout < 1.0:
        raise ValueError("holdout must be in the range [0, 1)")
    if num_workers < 1:
        raise ValueError("num_workers must be >= 1")
    if timeout < 1:
        raise ValueError("timeout must be >= 1")
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    if runs_per_query < 1:
        raise ValueError("runs_per_query must be >= 1")
    if not 0.0 <= trigger_threshold <= 1.0:
        raise ValueError("trigger_threshold must be in the range [0, 1]")

    name, original_description, content = parse_skill_md(skill_path)
    current_description = description_override or original_description

    # Split into train/test if holdout > 0
    if holdout > 0:
        train_indices, test_indices = split_eval_set(eval_set, holdout, seed=split_seed)
        train_set = [eval_set[idx] for idx in train_indices]
        test_set = [eval_set[idx] for idx in test_indices]
        if verbose:
            print(
                f"Split: {len(train_set)} train, {len(test_set)} test "
                f"(holdout={holdout}, seed={split_seed})",
                file=sys.stderr,
            )
    else:
        train_indices = list(range(len(eval_set)))
        test_indices = []
        train_set = eval_set
        test_set = []

    # Freeze split membership for the full run to prevent holdout leakage.
    train_indices = tuple(train_indices)
    test_indices = tuple(test_indices)

    if not train_indices:
        raise ValueError(
            "Train split is empty. Increase eval set size or reduce holdout."
        )
    if holdout > 0 and not test_indices:
        raise ValueError(
            "Test split is empty for holdout > 0. Increase eval set size or holdout fraction."
        )

    holdout_index_set = frozenset(test_indices)
    train_index_set = frozenset(train_indices)

    history = []
    exit_reason = "unknown"

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"Iteration {iteration}/{max_iterations}", file=sys.stderr)
            print(f"Description: {current_description}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)

        # Evaluate train + test together in one batch for parallelism
        all_queries = train_set + test_set
        all_indices = train_indices + test_indices
        t0 = time.time()
        all_results = run_eval(
            eval_set=all_queries,
            skill_name=name,
            description=current_description,
            num_workers=num_workers,
            timeout=timeout,
            run_dir=skill_path,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            model=model,
        )
        eval_elapsed = time.time() - t0

        if len(all_results["results"]) != len(all_indices):
            raise RuntimeError(
                "Eval result count mismatch: expected "
                f"{len(all_indices)}, got {len(all_results['results'])}"
            )

        # Leakage guard: holdout indices are fixed once from seeded split and
        # never re-sampled across iterations.
        if frozenset(test_indices) != holdout_index_set:
            raise RuntimeError("Holdout set changed during loop; aborting to prevent leakage")

        train_result_list = []
        test_result_list = []
        for eval_idx, result in zip(all_indices, all_results["results"]):
            if eval_idx in train_index_set:
                train_result_list.append(result)
            elif eval_idx in holdout_index_set:
                test_result_list.append(result)
            else:
                raise RuntimeError(f"Unexpected eval index in results: {eval_idx}")

        train_passed = sum(1 for r in train_result_list if r["pass"])
        train_total = len(train_result_list)
        train_summary = {"passed": train_passed, "failed": train_total - train_passed, "total": train_total}
        train_results = {"results": train_result_list, "summary": train_summary}

        if test_set:
            test_passed = sum(1 for r in test_result_list if r["pass"])
            test_total = len(test_result_list)
            test_summary = {"passed": test_passed, "failed": test_total - test_passed, "total": test_total}
            test_results = {"results": test_result_list, "summary": test_summary}
        else:
            test_results = None
            test_summary = None

        history.append({
            "iteration": iteration,
            "description": current_description,
            "train_passed": train_summary["passed"],
            "train_failed": train_summary["failed"],
            "train_total": train_summary["total"],
            "train_results": train_results["results"],
            "test_passed": test_summary["passed"] if test_summary else None,
            "test_failed": test_summary["failed"] if test_summary else None,
            "test_total": test_summary["total"] if test_summary else None,
            "test_results": test_results["results"] if test_results else None,
            # For backward compat with report generator
            "passed": train_summary["passed"],
            "failed": train_summary["failed"],
            "total": train_summary["total"],
            "results": train_results["results"],
        })

        # Write live report if path provided
        if live_report_path:
            partial_output = {
                "original_description": original_description,
                "best_description": current_description,
                "best_score": "in progress",
                "iterations_run": len(history),
                "holdout": holdout,
                "train_size": len(train_set),
                "test_size": len(test_set),
                "history": history,
            }
            live_report_path.write_text(generate_html(partial_output, auto_refresh=True, skill_name=name))

        if verbose:
            def print_eval_stats(label, results, elapsed):
                pos = [r for r in results if r["should_trigger"]]
                neg = [r for r in results if not r["should_trigger"]]
                tp = sum(r["triggers"] for r in pos)
                pos_runs = sum(r["runs"] for r in pos)
                fn = pos_runs - tp
                fp = sum(r["triggers"] for r in neg)
                neg_runs = sum(r["runs"] for r in neg)
                tn = neg_runs - fp
                total = tp + tn + fp + fn
                precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
                accuracy = (tp + tn) / total if total > 0 else 0.0
                print(f"{label}: {tp+tn}/{total} correct, precision={precision:.0%} recall={recall:.0%} accuracy={accuracy:.0%} ({elapsed:.1f}s)", file=sys.stderr)
                for r in results:
                    status = "PASS" if r["pass"] else "FAIL"
                    rate_str = f"{r['triggers']}/{r['runs']}"
                    print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:60]}", file=sys.stderr)

            print_eval_stats("Train", train_results["results"], eval_elapsed)
            if test_results is not None:
                print_eval_stats("Test ", test_results["results"], 0)

        if train_summary["failed"] == 0:
            exit_reason = f"all_passed (iteration {iteration})"
            if verbose:
                print(f"\nAll train queries passed on iteration {iteration}!", file=sys.stderr)
            break

        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            if verbose:
                print(f"\nMax iterations reached ({max_iterations}).", file=sys.stderr)
            break

        # Improve the description based on train results
        if verbose:
            print(f"\nImproving description...", file=sys.stderr)

        t0 = time.time()
        # Strip test scores from history so improvement model can't see them
        blinded_history = [
            {k: v for k, v in h.items() if not k.startswith("test_")}
            for h in history
        ]
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=train_results,
            history=blinded_history,
            model=model,
            run_dir=skill_path,
            log_dir=log_dir,
            iteration=iteration,
        )
        improve_elapsed = time.time() - t0

        if verbose:
            print(f"Proposed ({improve_elapsed:.1f}s): {new_description}", file=sys.stderr)

        current_description = new_description

    # Select the best iteration from train performance only.
    # This prevents repeatedly peeking at holdout scores when choosing the winner.
    best = select_best_iteration(history)
    best_score = f"{best['train_passed']}/{best['train_total']}"

    if verbose:
        print(f"\nExit reason: {exit_reason}", file=sys.stderr)
        print(f"Best score: {best_score} (iteration {best['iteration']})", file=sys.stderr)

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "selection_metric": "train",
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if test_set else None,
        "final_description": current_description,
        "iterations_run": len(history),
        "holdout": holdout,
        "split_seed": split_seed,
        "train_size": len(train_set),
        "test_size": len(test_set),
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="Run eval + improve loop")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override starting description")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max improvement iterations")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--holdout", type=float, default=0.4, help="Fraction of eval set to hold out for testing (0 to disable)")
    parser.add_argument("--split-seed", type=int, default=42, help="Random seed for deterministic train/test split")
    parser.add_argument("--model", required=True, help="Model for improvement")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    parser.add_argument("--report", default="auto", help="Generate HTML report at this path (default: 'auto' for temp file, 'none' to disable)")
    parser.add_argument("--results-dir", default=None, help="Save all outputs (results.json, report.html, log.txt) to a timestamped subdirectory here")
    args = parser.parse_args()

    if not 0.0 <= args.holdout < 1.0:
        print("Error: --holdout must be in the range [0, 1)", file=sys.stderr)
        sys.exit(1)
    if args.num_workers < 1:
        print("Error: --num-workers must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.timeout < 1:
        print("Error: --timeout must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.max_iterations < 1:
        print("Error: --max-iterations must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.runs_per_query < 1:
        print("Error: --runs-per-query must be >= 1", file=sys.stderr)
        sys.exit(1)
    if not 0.0 <= args.trigger_threshold <= 1.0:
        print("Error: --trigger-threshold must be between 0 and 1", file=sys.stderr)
        sys.exit(1)

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, _, _ = parse_skill_md(skill_path)

    # Set up live report path
    if args.report != "none":
        if args.report == "auto":
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            live_report_path = Path(tempfile.gettempdir()) / f"skill_description_report_{skill_path.name}_{timestamp}.html"
        else:
            live_report_path = Path(args.report)
        # Open the report immediately so the user can watch
        live_report_path.write_text("<html><body><h1>Starting optimization loop...</h1><meta http-equiv='refresh' content='5'></body></html>")
        webbrowser.open(str(live_report_path))
    else:
        live_report_path = None

    # Determine output directory (create before run_loop so logs can be written)
    if args.results_dir:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(args.results_dir) / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)
    else:
        results_dir = None

    log_dir = results_dir / "logs" if results_dir else None

    output = run_loop(
        eval_set=eval_set,
        skill_path=skill_path,
        description_override=args.description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        max_iterations=args.max_iterations,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        holdout=args.holdout,
        split_seed=args.split_seed,
        model=args.model,
        verbose=args.verbose,
        live_report_path=live_report_path,
        log_dir=log_dir,
    )

    # Save JSON output
    json_output = json.dumps(output, indent=2)
    print(json_output)
    if results_dir:
        (results_dir / "results.json").write_text(json_output)

    # Write final HTML report (without auto-refresh)
    if live_report_path:
        live_report_path.write_text(generate_html(output, auto_refresh=False, skill_name=name))
        print(f"\nReport: {live_report_path}", file=sys.stderr)

    if results_dir and live_report_path:
        (results_dir / "report.html").write_text(generate_html(output, auto_refresh=False, skill_name=name))

    if results_dir:
        print(f"Results saved to: {results_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()

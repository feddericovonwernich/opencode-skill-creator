import tempfile
import unittest
from pathlib import Path

from scripts.run_loop import run_loop, select_best_iteration, split_eval_set


class RunLoopSplitTests(unittest.TestCase):
    def test_split_keeps_train_samples_per_non_singleton_class(self) -> None:
        eval_set = [
            {"query": "a", "should_trigger": True},
            {"query": "b", "should_trigger": True},
            {"query": "c", "should_trigger": False},
            {"query": "d", "should_trigger": False},
        ]

        train, test = split_eval_set(eval_set, holdout=0.99, seed=42)

        self.assertGreaterEqual(len(train), 2)
        self.assertEqual(len(test), 2)

    def test_split_keeps_singleton_class_in_train(self) -> None:
        eval_set = [
            {"query": "singleton-pos", "should_trigger": True},
            {"query": "neg-1", "should_trigger": False},
            {"query": "neg-2", "should_trigger": False},
        ]

        train, _ = split_eval_set(eval_set, holdout=0.5, seed=42)

        self.assertIn(0, train)

    def test_run_loop_rejects_holdout_one(self) -> None:
        with self.assertRaises(ValueError):
            run_loop(
                eval_set=[],
                skill_path=Path("/tmp/unused"),
                description_override=None,
                num_workers=1,
                timeout=1,
                max_iterations=1,
                runs_per_query=1,
                trigger_threshold=0.5,
                holdout=1.0,
                split_seed=42,
                model="test-model",
                verbose=False,
            )

    def test_run_loop_rejects_empty_test_set_when_holdout_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_path = Path(temp_dir) / "demo-skill"
            skill_path.mkdir()
            (skill_path / "SKILL.md").write_text(
                "---\n"
                "name: demo-skill\n"
                "description: Demo description\n"
                "---\n\n"
                "# Demo\n",
                encoding="utf-8",
            )

            eval_set = [
                {"query": "pos", "should_trigger": True},
                {"query": "neg", "should_trigger": False},
            ]

            with self.assertRaises(ValueError):
                run_loop(
                    eval_set=eval_set,
                    skill_path=skill_path,
                    description_override=None,
                    num_workers=1,
                    timeout=1,
                    max_iterations=1,
                    runs_per_query=1,
                    trigger_threshold=0.5,
                    holdout=0.4,
                    split_seed=42,
                    model="test-model",
                    verbose=False,
                    live_report_path=None,
                    log_dir=None,
                )

    def test_select_best_iteration_uses_train_not_test(self) -> None:
        history = [
            {
                "iteration": 1,
                "train_passed": 3,
                "train_total": 4,
                "test_passed": 4,
                "test_total": 4,
            },
            {
                "iteration": 2,
                "train_passed": 4,
                "train_total": 4,
                "test_passed": 0,
                "test_total": 4,
            },
        ]

        best = select_best_iteration(history)

        self.assertEqual(best["iteration"], 2)

    def test_select_best_iteration_tiebreaks_to_earlier_iteration(self) -> None:
        history = [
            {
                "iteration": 1,
                "train_passed": 2,
                "train_total": 3,
            },
            {
                "iteration": 2,
                "train_passed": 2,
                "train_total": 3,
            },
        ]

        best = select_best_iteration(history)

        self.assertEqual(best["iteration"], 1)


if __name__ == "__main__":
    unittest.main()

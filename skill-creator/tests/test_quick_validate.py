import tempfile
import unittest
from pathlib import Path

from scripts.quick_validate import validate_skill


class QuickValidateTests(unittest.TestCase):
    def _write_skill(self, root: Path, directory_name: str, frontmatter: str) -> Path:
        skill_dir = root / directory_name
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            f"---\n{frontmatter}\n---\n\n# Skill\n",
            encoding="utf-8",
        )
        return skill_dir

    def test_accepts_valid_minimal_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = self._write_skill(
                root,
                "valid-skill",
                "name: valid-skill\ndescription: Useful one-line description",
            )

            is_valid, message = validate_skill(skill_dir)

        self.assertTrue(is_valid)
        self.assertEqual(message, "Skill is valid!")

    def test_rejects_name_directory_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = self._write_skill(
                root,
                "actual-directory-name",
                "name: different-name\ndescription: Useful one-line description",
            )

            is_valid, message = validate_skill(skill_dir)

        self.assertFalse(is_valid)
        self.assertIn("must match the skill directory name", message)

    def test_rejects_non_string_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = self._write_skill(
                root,
                "compatibility-type-skill",
                "name: compatibility-type-skill\ndescription: Useful one-line description\ncompatibility:\n  mode: strict",
            )

            is_valid, message = validate_skill(skill_dir)

        self.assertFalse(is_valid)
        self.assertIn("Compatibility must be a string", message)


if __name__ == "__main__":
    unittest.main()

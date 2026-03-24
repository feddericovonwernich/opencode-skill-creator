#!/usr/bin/env python3
"""
Quick validation script for skills - minimal version
"""

import re
import sys
from pathlib import Path

import yaml


ALLOWED_FRONTMATTER_KEYS = {"name", "description", "license", "compatibility", "metadata"}
REQUIRED_FRONTMATTER_KEYS = {"name", "description"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
PLACEHOLDER_DESCRIPTION_PATTERNS = (
    re.compile(r"\b(todo|tbd|fixme)\b", re.IGNORECASE),
    re.compile(r"\byour\s+description\s+here\b", re.IGNORECASE),
    re.compile(r"\badd\s+description\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
)

def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path).resolve()

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    try:
        content = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, f"Unable to read SKILL.md: {e}"
    if not content.startswith('---'):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    # Check for unexpected properties
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_FRONTMATTER_KEYS
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            "Allowed properties are: "
            f"{', '.join(sorted(ALLOWED_FRONTMATTER_KEYS))}"
        )

    # Check required fields
    missing_required = sorted(REQUIRED_FRONTMATTER_KEYS - set(frontmatter.keys()))
    if missing_required:
        return False, f"Missing required frontmatter key(s): {', '.join(missing_required)}"

    # Extract name for validation
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if not name:
        return False, "Name cannot be empty"
    if not NAME_PATTERN.match(name):
        return False, (
            f"Name '{name}' must be kebab-case using lowercase letters, digits, "
            "and single hyphens between segments"
        )
    if len(name) > MAX_NAME_LENGTH:
        return False, f"Name is too long ({len(name)} characters). Maximum is {MAX_NAME_LENGTH} characters."

    directory_name = skill_path.name
    if name != directory_name:
        return False, (
            f"Name '{name}' must match the skill directory name '{directory_name}'"
        )

    # Extract and validate description
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if not description:
        return False, "Description cannot be empty"

    if '<' in description or '>' in description:
        return False, "Description cannot contain angle brackets (< or >)"

    if len(description) > MAX_DESCRIPTION_LENGTH:
        return False, (
            f"Description is too long ({len(description)} characters). "
            f"Maximum is {MAX_DESCRIPTION_LENGTH} characters."
        )

    if any(ch in description for ch in ('\n', '\r', '\t')):
        return False, "Description must be a single clean line without tabs or newlines"

    if '  ' in description:
        return False, "Description should not contain repeated spaces"

    for pattern in PLACEHOLDER_DESCRIPTION_PATTERNS:
        if pattern.search(description):
            return False, "Description appears to contain placeholder text"

    if "license" in frontmatter and not isinstance(frontmatter["license"], str):
        return False, f"License must be a string, got {type(frontmatter['license']).__name__}"

    if "compatibility" in frontmatter and not isinstance(frontmatter["compatibility"], str):
        return False, f"Compatibility must be a string, got {type(frontmatter['compatibility']).__name__}"

    if "metadata" in frontmatter and not isinstance(frontmatter["metadata"], dict):
        return False, f"Metadata must be an object/map, got {type(frontmatter['metadata']).__name__}"

    return True, "Skill is valid!"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)
    
    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)

---
name: skill-creator
description: Create new skills, modify and improve existing skills, and measure skill performance in OpenCode. Use when users want to create a skill from scratch, edit or optimize an existing skill, run evals to test behavior, benchmark with variance analysis, or optimize a skill description for better triggering accuracy.
---

# Skill Creator

Create or improve skills using a practical loop:

1. Clarify intent and success criteria.
2. Draft or revise the skill.
3. Run realistic eval prompts (with baseline comparisons when useful).
4. Review qualitative outputs and quantitative metrics with the user.
5. Iterate on the skill and repeat.
6. Optimize description triggering once behavior is solid.

Use this skill to meet the user where they are in that loop. If they already have a draft, jump directly to eval and iteration.

## Communicating with the user

Adapt language to user expertise. Default to clear, practical wording and brief definitions when needed.

- Terms like "evaluation" and "benchmark" are usually fine.
- Terms like "assertion" or detailed schema jargon may need a one-line explanation for less technical users.
- Prefer concrete examples over abstract process talk.

## Creating a skill

### Capture intent

Start from the conversation history when possible, then fill gaps with targeted questions:

1. What should this skill enable OpenCode to do?
2. When should it trigger?
3. What output format is expected?
4. Should this skill have eval cases? Recommend yes for objectively testable tasks and optional for subjective ones.

### Interview and research

Collect edge cases, dependencies, input/output constraints, representative files, and success criteria before writing eval prompts.

### Write `SKILL.md`

Fill frontmatter and instructions from the interview:

- `name`: skill identifier. Keep stable for updates.
- `description`: trigger guidance plus what the skill does. Include context cues so triggering is reliable.
- `compatibility`: optional tool/dependency notes.
- Body: practical instructions with rationale, not rigid boilerplate.

### Anatomy of a skill

```text
skill-name/
|-- SKILL.md
|-- scripts/        (optional)
|-- references/     (optional)
`-- assets/         (optional)
```

### Writing patterns

- Use imperative instructions with concise rationale.
- Keep the main body focused; move long references into `references/`.
- Include examples for ambiguous formats.
- Avoid overfitting to one test prompt.

## Test cases

After drafting, create 2-3 realistic prompts and confirm them with the user.

Save to `evals/evals.json` first without assertions:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

See `references/schemas.md` for full structures.

## Running and evaluating test cases

Do this sequence end-to-end. Do not stop halfway.

Store results in a sibling workspace directory named `skill-name-workspace/`, then per iteration:

```text
skill-name-workspace/
`-- iteration-1/
    |-- eval-0/
    |   |-- with_skill/
    |   `-- without_skill/  (or old_skill/ for existing-skill upgrades)
    `-- eval-1/
```

### Step 1: Launch runs for skill and baseline

For each eval prompt, run:

- **With skill**: current skill version.
- **Baseline**:
  - New skill creation: no skill.
  - Existing skill improvement: snapshot old skill before edits and use that snapshot.

Launch all evals and both variants as close together as possible to reduce time drift.

Create `eval_metadata.json` per eval:

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name",
  "prompt": "Task prompt",
  "assertions": []
}
```

### Step 2: Draft assertions while runs are in progress

Write objective assertions with clear names. Keep subjective quality in human review rather than forcing brittle assertions.

Update both:

- `evals/evals.json`
- each `eval_metadata.json`

### Step 3: Capture timing and token data immediately

When each run completes, write `timing.json` in that run directory:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

### Step 4: Grade, aggregate, and review

1. Grade each run and save `grading.json`.
2. Aggregate benchmark results:

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

3. Do an analyst pass for discriminating assertions, high-variance evals, and token/time tradeoffs.
4. Generate reviewer output with `scripts/generate_report.py` or `eval-viewer/generate_review.py` (preferred when available), then have the user review outputs plus benchmark metrics.

### Step 5: Read user feedback and close the loop

Read `feedback.json` (or equivalent collected review notes). Empty feedback generally means the case is acceptable. Focus edits on concrete complaints and repeated failure modes.

## Improving the skill

This is the core work.

1. Generalize from feedback; do not overfit to a tiny eval set.
2. Keep prompts lean; remove low-value instructions.
3. Explain why steps matter so behavior transfers to new prompts.
4. Look for repeated work and bundle reusable scripts in `scripts/`.

Iteration loop:

1. Apply revisions.
2. Rerun evals into `iteration-N+1/` with baseline.
3. Review outputs and benchmark deltas.
4. Gather feedback.
5. Repeat until quality stabilizes.

Stop when the user is satisfied, feedback is effectively empty, or additional iterations are not producing meaningful gains.

## Advanced: Blind comparison

For rigorous A/B checks between versions, use blind comparison (see `agents/comparator.md`) and analyze outcomes with `agents/analyzer.md`.

Use this when users ask whether a new version is actually better, especially when benchmark deltas are small.

## Description optimization

Skill triggering depends primarily on frontmatter `description`. After behavior is solid, optimize description accuracy.

### Step 1: Create trigger eval queries

Create around 20 realistic queries with both positives and negatives:

```json
[
  {"query": "user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

Favor realistic near-miss negatives over obviously unrelated negatives.

### Step 2: Review eval set with user

Use `assets/eval_review.html`:

1. Inject eval JSON and current description placeholders.
2. Open the file for user editing.
3. Import the exported eval set back into the workspace.

### Step 3: Run optimization loop

Run:

```bash
python -m scripts.run_loop \
  --eval-set <path-to-eval-set.json> \
  --skill-path <path-to-skill> \
  --model <current-session-model-id> \
  --max-iterations 5 \
  --verbose
```

This evaluates trigger behavior, proposes revised descriptions, and reports best description using held-out performance.

### Step 4: Apply best result

Update `SKILL.md` frontmatter with `best_description`, then show before/after plus score changes.

## Packaging

When requested, package the skill:

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

Return the resulting `.skill` path.

## Reference files

- `agents/grader.md`: assertion grading guidance
- `agents/comparator.md`: blind comparison process
- `agents/analyzer.md`: benchmark/result analysis patterns
- `references/schemas.md`: expected JSON structures

## Core loop reminder

1. Define scope.
2. Draft or revise skill.
3. Run with-skill and baseline evals.
4. Review outputs and benchmark data with the user.
5. Iterate until quality is stable.
6. Optimize description triggering.
7. Package when the user asks.

# UI and README copy cleanup implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AI-styled public copy with direct language while preserving every fact, route, calculation, and interface behavior.

**Architecture:** Treat the README, public map, and Studio as three separate copy surfaces. Add narrow regression patterns to the public-copy gate. Change source strings and check each surface before the full repository check.

**Tech Stack:** Markdown, single-file HTML and JavaScript, Python data builders, React and TypeScript, project QA scripts, Playwright.

## Global Constraints

- Keep all facts, numbers, links, limitations, routes, data contracts, commands, and calculation behavior unchanged.
- Keep technical power-market terms when they carry precise meaning.
- Do not change layout, information architecture, visual styling, model code, or calculation logic.
- Use direct, neutral language without slogans, staged punchlines, sales copy, anthropomorphism, or instructions to choose this project over another.
- Preserve unrelated work and stage only the files changed by each task.

---

### Task 1: Rewrite the README front door

**Files:**
- Change: `tests/qa_gate.py`
- Change: `README.md`
- Test: `tests/qa_gate.py`
- Test: `tests/test_readme_views.py`
- Test: `scripts/verify_claims.py`

**Interfaces:**
- Consumes: the existing `TARGETS`, `AI_JARGON`, and `OVERWROUGHT` checks in `tests/qa_gate.py`.
- Produces: a README with neutral product descriptions and regression checks for the phrases that prompted this cleanup.

- [ ] **Step 1: Add README-specific failing copy checks**

Add these patterns beside the other voice checks in `tests/qa_gate.py` and scan them in `scan()`:

```python
AI_TELLS = [
    ("persona-door heading", r"\bpick the door that fits you\b"),
    ("staged receipts contrast", r"\breceipts,\s*not estimates\b"),
    ("choose-us instruction", r"\bpoint the engine at your own system, not at ours\b"),
    ("competitor recommendation", r"\bfor everything else on the list, pick them\b"),
    ("reader payment metaphor", r"\bvisitor pays for them\b"),
]
```

Report failures as `AI-tell '<label>'` so they are distinct from banned factual claims.

- [ ] **Step 2: Run the gate and check that the new checks fail**

Run: `python3 tests/qa_gate.py`

Expected: FAIL entries for `README.md` naming the new AI-tell labels.

- [ ] **Step 3: Rewrite the README copy**

Use these direct replacements as the baseline, then audit the rest of the file for the same patterns:

```text
Pick the door that fits you -> Choose an interface
Add 3,000 MW ... in one drag -> Example scenario: 3,000 MW of added Luzon demand
A nightly archive, receipts ... -> What the project includes
Receipts, not estimates -> Recorded grid constraints
This front door downloads ... visitor pays ... -> The README embeds ...
PyPSA-PH models ... This one ... -> Comparison with related power-system tools
It is a three-zone ... not ... -> Model scope
web/for-analysts.html link text -> six documented model limits
Point the engine ... -> Use your own system data
```

Replace the competitor conclusion with one factual sentence about the nightly IEMOP archive and published replay error. Keep the comparison table balanced and remove `What this has`, `brings its own system`, and all advice about which tool to pick.

- [ ] **Step 4: Run the README checks**

Run:

```bash
python3 tests/qa_gate.py
python3 /Users/xavier/.claude/skills/deslop/references/deslop_lint.py --mode prose --file README.md
python3 tests/test_readme_views.py
python3 scripts/verify_claims.py
git diff --check
```

Expected: the QA gate, view catalog checks, claim oracle, and diff check pass. Review each prose-linter advisory against the design rather than replacing exact domain language.

- [ ] **Step 5: Commit the README cleanup**

Stage only `README.md` and `tests/qa_gate.py`. Commit with `Rewrite the README in direct language`.

### Task 2: Rewrite the public map copy and its built text

**Files:**
- Change: `tests/qa_gate.py`
- Change: `web/index.html`
- Change: `pipeline/build_data.py`
- Change: `web/data/answers.json`
- Change: `web/data/findings.json`
- Test: `tests/qa_gate.py`
- Test: `tests/test_data.py`
- Test: `scripts/verify_claims.py`

**Interfaces:**
- Consumes: `build_answers()` and `build_findings()` in `pipeline/build_data.py`, which supply the map question rail and findings drawer.
- Produces: direct map labels and built JSON that matches the Python source strings.

- [ ] **Step 1: Add map-specific failing copy checks**

Extend `AI_TELLS` with:

```python
("paper-practice contrast", r"\bone market on paper, three prices in practice\b"),
("story framing", r"\bthe same story with unit names\b"),
("normal-state slogan", r"\bthin is the normal state\b"),
("margin metaphor", r"\btakes? \d+% of the margin with it\b"),
```

- [ ] **Step 2: Run the gate and check that the map checks fail**

Run: `python3 tests/qa_gate.py`

Expected: FAIL entries from `index.html`, `answers.json`, or `findings.json` for each new pattern present in the current copy.

- [ ] **Step 3: Rewrite static map labels and messages**

In `web/index.html`, use compact labels such as `Details`, `Archive findings`, `Recorded constraint intervals`, and `Constrained-on units`. Replace `Your scenario moves...` with a neutral `Scenario clearing price...` result. Keep question labels, source labels, units, accessibility text, error meaning, and all DOM identifiers unchanged.

- [ ] **Step 4: Rewrite built question and finding copy at the source**

In `pipeline/build_data.py`, use these question titles:

```text
Can supply cover additional data-center demand?
Where can new demand connect?
How does added demand affect prices?
```

Use literal finding tags such as `Supply margin`, `Reserve record`, and `Regional prices`. Replace rhetorical titles and blurbs with measured statements. Apply the same text to `web/data/answers.json` and `web/data/findings.json` so the committed output matches the builder.

- [ ] **Step 5: Run the map checks**

Run:

```bash
python3 tests/qa_gate.py
python3 tests/test_data.py
python3 scripts/verify_claims.py
python3 /Users/xavier/.claude/skills/deslop/references/deslop_lint.py --mode ui --file web/index.html
git diff --check
```

Expected: all checks pass. `verify_claims.py` reports the current guarded-claim count without rewriting factual values.

- [ ] **Step 6: Commit the map cleanup**

Stage only `tests/qa_gate.py`, `web/index.html`, `pipeline/build_data.py`, `web/data/answers.json`, and `web/data/findings.json`. Commit with `Rewrite the map copy in direct language`.

### Task 3: Replace sentence-like Studio headings with direct labels

**Files:**
- Change: `tests/qa_gate.py`
- Change if the audit finds a tell: `studio/index.html`
- Change: `studio/src/studio/BackcastView.tsx`
- Change: `studio/src/studio/CaptureView.tsx`
- Change: `studio/src/studio/CrossRunView.tsx`
- Change: `studio/src/studio/DistributionView.tsx`
- Change: `studio/src/studio/EmissionsView.tsx`
- Change: `studio/src/studio/ExpansionView.tsx`
- Change: `studio/src/studio/FutureYearView.tsx`
- Change: `studio/src/studio/NodalView.tsx`
- Change: `studio/src/studio/PortfolioView.tsx`
- Change: `studio/src/studio/Rtdoe5View.tsx`
- Change: `studio/src/studio/RunsView.tsx`
- Change: `studio/src/studio/SitesView.tsx`
- Change: `studio/src/studio/SweepView.tsx`
- Change: `studio/src/studio/UcProbeView.tsx`
- Change: `studio/src/studio/model-views.tsx`
- Change: `studio/src/studio/views.tsx`
- Test: matching `studio/src/**/*.test.ts` files when assertions pin changed copy
- Test: `tests/qa_gate.py`

**Interfaces:**
- Consumes: existing React `Panel`, `StatTile`, `EmptyNote`, and navigation components. Their props and rendering stay unchanged.
- Produces: shorter headings and helper text with the same data inputs, units, and actions.

- [ ] **Step 1: Add Studio-specific failing copy checks**

Extend `AI_TELLS` with current sentence templates:

```python
("hidden-result headline", r"\bthe average price hides a spread\b|\ban hourly average hides that\b"),
("capacity-eating metaphor", r"\bevery added mw eats spare capacity\b"),
("technology-earnings contrast", r"\bwhat a technology earns is not the market average\b"),
("scenario-causality slogan", r"\bevery scenario solves the same model, so\b"),
("saved-run causality slogan", r"\beach saved run keeps its own settings, so\b"),
```

- [ ] **Step 2: Run the gate and check that the Studio checks fail**

Run: `python3 tests/qa_gate.py`

Expected: FAIL entries naming the affected `.tsx` files.

- [ ] **Step 3: Rewrite Studio headings and helper text**

Use noun phrases or measured result statements. Representative replacements:

```text
The average price hides... -> Modeled and recorded price-duration curves
What a technology earns... -> Technology capture prices
Every scenario solves... -> Scenario results comparison
Each saved run keeps... -> Saved-run metrics
Every added MW eats... -> Spare capacity as demand increases
The operator dispatches every 5 minutes... -> 5-minute and hourly price ranges
```

Apply the same treatment to other sentence-like headings found in the listed files. Keep causal explanations in subtitles when they help interpretation. Keep warnings, disclaimers, model limitations, error messages, control labels, and field names precise.

- [ ] **Step 4: Run focused Studio checks**

Run:

```bash
python3 tests/qa_gate.py
cd studio && npm test -- --run
cd studio && npx prettier --check "src/**/*.{ts,tsx,css}"
cd studio && npm run build
git diff --check
```

Expected: the copy gate, Studio tests, formatting check, production build, and diff check pass.

- [ ] **Step 5: Commit the Studio cleanup**

Stage only `tests/qa_gate.py` and the Studio files changed in this task. Commit with `Rewrite Studio headings and guidance`.

### Task 4: Check the complete public experience

**Files:**
- Check: `README.md`
- Check: `web/index.html`
- Check: `web/data/answers.json`
- Check: `web/data/findings.json`
- Check: `studio/src/**`
- Check: `docs/superpowers/specs/2026-08-12-ui-readme-copy-cleanup-design.md`
- Check: `docs/superpowers/plans/2026-08-12-ui-readme-copy-cleanup.md`

**Interfaces:**
- Consumes: the three cleaned public surfaces and all existing repository checks.
- Produces: fresh automated and visual evidence that the copy cleanup did not change behavior or break responsive layouts.

- [ ] **Step 1: Run full automated verification**

Run:

```bash
python3 scripts/verify_claims.py
make qa
cd studio && npx prettier --check "src/**/*.{ts,tsx,css}"
```

Expected: every command exits zero.

- [ ] **Step 2: Run the local browser checks**

Start the project with `make serve`, then run:

```bash
make e2e BASE=http://127.0.0.1:8789
```

Expected: all public-map and Studio browser checks pass.

- [ ] **Step 3: Inspect desktop and mobile screens**

Capture the public map and Studio at one desktop width and at 390 px. Inspect headings, navigation, result cards, empty states, and the README-rendered copy for clipping, awkward wrapping, stale phrases, or changed hierarchy.

- [ ] **Step 4: Audit the final diff**

Run:

```bash
git status --short
git diff --check HEAD~3..HEAD
git diff --stat HEAD~3..HEAD
git log -4 --oneline
```

Expected: only the design, plan, copy sources, directly related built JSON, and regression checks changed. No calculation or layout code changed.

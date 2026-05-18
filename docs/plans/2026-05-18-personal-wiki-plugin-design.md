# Personal Wiki Plugin Design

> **For Hermes:** Design-only plan. Do not implement until the owner explicitly approves the implementation phase. When implementing, use `subagent-driven-development` task-by-task and request adviser/reviewer review before running any write-mode action against a live personal wiki.

**Goal:** Build a generic/shareable Hermes plugin that helps a user bootstrap, validate, and maintain a Git/Obsidian personal wiki using a reusable source-first curation method, without exporting private content from any source installation.

**Architecture:** Ship a conservative `personal-wiki` general plugin with a CLI command, bundled skill, templates, and a deterministic validator/scaffolder. v1 is dry-run/read-only-first: it creates a new vault skeleton in an empty target, audits an existing vault safely, and validates schema/navigation/provenance. It must not auto-ingest private data, auto-start gateways/crons, sync to GitHub, or mutate an existing vault.

**Tech Stack:** Hermes plugin system (`plugin.yaml`, `register(ctx)`, `ctx.register_cli_command`, `ctx.register_skill`), Python stdlib, Markdown/YAML frontmatter, Obsidian-compatible folders/templates, pytest.

---

## Design Decision

Implement this as a **Hermes general plugin** named `personal-wiki`, not as a built-in skill only.

Why:

- A skill alone can describe the method but cannot scaffold or validate files.
- A plugin can ship:
  - a namespaced skill (`personal-wiki:personal-wiki`);
  - templates and starter vault files;
  - a CLI command (`hermes personal-wiki ...`);
  - deterministic validators and dry-run audit flows.
- A plugin remains opt-in via `plugins.enabled`, so third-party/local code does not run automatically.
- `personal-wiki` is the stable enable/config key; avoid `-base` unless we later create downstream inheritance plugins.

v1 should avoid registering LLM-callable tools. The CLI + skill surface is safer and enough for bootstrap/testing. Tool registration can be a v2 addition after the bootstrap/validator stabilizes.

## Non-Goals for v1

- No private content from any source wiki.
- No names, chat/group identifiers, emails, phone numbers, client/project names, or local paths from a source installation.
- No gateway configuration.
- No cron jobs created automatically.
- No auto-sync to GitHub.
- No ingestion from chat/session memory.
- No destructive archive/delete/move operations.
- No database, embedding index, or background crawler.
- No assumption that Obsidian is installed.

## Plugin Layout

Create:

```text
plugins/personal-wiki/
├── plugin.yaml
├── __init__.py
├── cli.py
├── scaffold.py
├── validator.py
├── sanitize.py
├── README.md
├── SKILL.md
└── templates/
    ├── vault/
    │   ├── 00 System/SCHEMA.md
    │   ├── 00 System/index.md
    │   ├── 00 System/log.md
    │   ├── 00 System/dashboards/home.md
    │   ├── 00 System/dashboards/projects.md
    │   ├── 00 System/dashboards/areas.md
    │   ├── 00 System/dashboards/open-loops.md
    │   ├── 00 System/dashboards/wiki-health.md
    │   ├── 01 Inbox/quick-capture.md
    │   ├── 01 Inbox/drafts/.gitkeep
    │   ├── 02 Raw/.gitkeep
    │   ├── 10 Areas/.gitkeep
    │   ├── 20 Resources/.gitkeep
    │   ├── 30 Decisions/.gitkeep
    │   ├── 40 Reviews/.gitkeep
    │   ├── 50 Queries/.gitkeep
    │   └── 99 Archive/.gitkeep
    └── notes/
        ├── area.md
        ├── project.md
        ├── resource.md
        ├── decision.md
        ├── review.md
        └── submission.md
```

Tests:

```text
tests/plugins/test_personal_wiki_scaffold.py
tests/plugins/test_personal_wiki_validator.py
tests/plugins/test_personal_wiki_plugin.py
tests/hermes_cli/test_personal_wiki_cli.py
```

## Manifest

`plugins/personal-wiki/plugin.yaml`:

```yaml
name: personal-wiki
version: 0.1.0
description: "Bootstrap and validate a generic Git/Obsidian personal wiki with source-first curation, PARA-inspired areas/projects, dashboards, templates, and privacy-first rules."
author: NousResearch
kind: standalone
```

Notes:

- `kind: standalone` means this is a general opt-in plugin gated by `plugins.enabled`.
- Do **not** add declarative `provides_cli` or `provides_skills`; Hermes currently registers CLI commands and plugin skills at runtime via `ctx.register_cli_command(...)` and `ctx.register_skill(...)`.
- Do **not** use `requires_env` in v1. The plugin should work offline and without credentials.

## Registration

`plugins/personal-wiki/__init__.py` should register:

```python
from pathlib import Path

from .cli import personal_wiki_command, register_cli


def register(ctx) -> None:
    ctx.register_skill(
        "personal-wiki",
        Path(__file__).with_name("SKILL.md"),
        "Use when bootstrapping, validating, or maintaining a generic personal wiki.",
    )
    ctx.register_cli_command(
        name="personal-wiki",
        help="Bootstrap and validate a generic personal wiki vault",
        setup_fn=register_cli,
        handler_fn=personal_wiki_command,
        description="Create, audit, and validate a Git/Obsidian personal wiki skeleton.",
    )
```

Notes:

- This may be the first bundled plugin to rely on `ctx.register_skill`; include an end-to-end integration test for `skill_view(name="personal-wiki:personal-wiki")`.
- Keep `__init__.py` import cheap and side-effect-free. Importing the plugin module must not read user vaults, write files, or inspect environment-specific paths.
- No tool schemas in v1.

## Read-Only Safety Contract

All commands that inspect an existing wiki (`audit`, `validate`, `doctor`) must follow the same filesystem safety rules:

- Resolve all paths under the supplied root and refuse to follow symlinks that escape the root.
- Skip `.git/`, `.obsidian/workspace*.json`, caches, build artifacts, virtualenvs, and other hidden state that may contain transient/private UI history.
- Refuse named pipes, sockets, block devices, character devices, and any non-regular file.
- Enforce a per-file max read size, default 1 MiB; report skipped files by path/reason only.
- Never print raw secret-like matches. Report `path`, `line`, `kind`, and a redacted marker only.
- Use `yaml.safe_load` for frontmatter and `--vars` YAML; reject unsafe tags.
- Support a plan/inventory mode that lists files that would be read before content inspection.

## CLI Surface

```bash
hermes personal-wiki init PATH [--title TITLE] [--owner-label LABEL] [--dry-run]
hermes personal-wiki validate PATH [--json]
hermes personal-wiki audit PATH [--json] [--plan]
hermes personal-wiki doctor PATH
hermes personal-wiki render-template NAME --output PATH [--vars vars.yaml]
```

### `init`

Creates a starter vault only if `PATH` is empty or missing. v1 should not include `--force` unless tests cover every overwrite path.

Behavior:

- create folder layout;
- render generic templates;
- write neutral schema/index/log;
- optionally set `title` in frontmatter and headings;
- never insert private examples;
- emit a summary of created files;
- support `--dry-run` that prints the file plan without writing.

### `validate`

Checks a vault against the generic schema:

- required directories exist;
- required system files exist;
- Markdown files in curated zones have YAML frontmatter;
- allowed `type` values;
- project pages include required sections;
- raw sources have `type: source`, `ingested`, and `sha256` when applicable;
- wikilinks are parsed with support for `[[Note#Heading|Alias]]`, `[[Note.md]]`, `[[folder/Note]]`, and embedded `![[Note]]`;
- broken wikilinks are reported as warnings or errors depending on severity;
- obvious secret-like strings are flagged as high-risk warnings, not printed raw.

Initial secret heuristics:

- AWS access key: `AKIA[0-9A-Z]{16}`
- GitHub tokens: `gh[pousr]_[A-Za-z0-9_]{30,}`
- Slack tokens: `xox[baprs]-[A-Za-z0-9-]{20,}`
- Generic assignment: `(api[_-]?key|password|passwd|token|secret)\s*[:=]`
- Private key header: `-----BEGIN .*PRIVATE KEY-----`

Redaction format:

```json
{"path":"relative/path.md","line":42,"kind":"github_token","redacted":true}
```

No raw token value in text or JSON output.

Return codes:

- `0`: valid;
- `1`: validation errors;
- `2`: unsafe invocation / missing path / parse failure.

### `audit`

Read-only report for existing wikis. This is the command to run against the existing private wiki first.

Output groups:

- structure coverage;
- schema deviations;
- possible local-only/private content in export candidates;
- empty placeholder noise;
- pages with low confidence or `needs-review`;
- pages that could become generic improvements.

`audit --plan` prints the file inventory that would be read, with skip reasons, without reading file contents. Use this before auditing a private wiki.

### `doctor`

Convenience wrapper:

- runs `audit --plan` summary;
- runs `audit` and `validate` only after explicit CLI invocation;
- prints Obsidian/Git readiness hints;
- suggests next safe action.

### `render-template`

Renders one note template for users/agents who want a new area/project/decision page without copying from docs.

Rules:

- `--vars vars.yaml` uses `yaml.safe_load` only;
- unresolved placeholders fail the command;
- output path must be under the caller-supplied destination root when a root is provided.

## Bundled Skill

`plugins/personal-wiki/SKILL.md` should be the generic skill a new user/agent loads as:

```python
skill_view(name="personal-wiki:personal-wiki")
```

It should cover:

- when to use the plugin;
- folder model;
- source-first curation;
- project-inside-area rule;
- frontmatter requirements;
- privacy and secret handling;
- draft/inbox curation without automated ingestion;
- how to use `hermes personal-wiki init|audit|validate|doctor`;
- how to submit sanitized improvements back upstream.

Use neutral terms: `user`, `source wiki`, `curator`, `private project`, `review queue`.

## Template Rules

All templates must be neutral:

Good:

```markdown
# Personal Wiki

This vault stores durable orientation: areas, projects, decisions, reusable resources, sources, and reviews.
```

Bad:

```markdown
# A named person's private wiki
```

Use placeholder variables only where needed:

- `{{vault_title}}`
- `{{owner_label}}`
- `{{created_date}}`

No hidden defaults containing private names or installation-specific paths.

## Sanitization Guard

`sanitize.py` should support both generic checks and local/private checks.

Shipped default:

```python
FORBIDDEN_EXPORT_STRINGS = []
```

Private/local denylist options:

1. Load optional plaintext patterns from a gitignored path such as `$HERMES_HOME/personal-wiki/denylist.local.txt`; or
2. Load SHA-256 hashes from a gitignored path and compare candidate strings by hash.

Recommendation for v1: implement the optional plaintext local file because it is simple and never committed. CI should support an environment variable pointing to a local denylist file. The plugin repository must not commit private names as source strings.

Important nuance: local denylist checks apply only to shipped plugin templates/skill/README during development and CI. They do not imply that a user's own vault is invalid because it contains that user's own private names.

## Test Strategy

### Unit and integration tests

1. `init --dry-run` returns planned files and writes nothing.
2. `init PATH` creates expected layout in a temp dir.
3. `init PATH` refuses non-empty dirs without overwrite support.
4. Rendered starter vault passes `validate`.
5. `validate` catches missing frontmatter.
6. `validate` catches invalid note type.
7. `validate` catches broken wikilinks.
8. `validate` does not print raw secret-like values.
9. `audit --json` on a fixture containing fake AWS/GitHub tokens omits raw token values.
10. Optional local sanitize denylist rejects forbidden strings in shipped templates/skill/README without committing private names.
11. Plugin registration exposes CLI command and namespaced skill.
12. Plugin module imports cleanly with no user-vault file I/O when not enabled.
13. `audit` refuses to follow symlinks that escape the target root.
14. `audit` skips files larger than the configured max read size.
15. `render-template --vars vars.yaml` rejects unsafe YAML tags such as `!!python/object`.
16. Rendered starter vault has zero unresolved `{{ ... }}` placeholders.
17. `validate --json` output conforms to a documented JSON schema or snapshot.
18. Wikilink parser handles `[[Note#Heading|Alias]]`, `[[Note.md]]`, `[[folder/Note]]`, and embedded `![[Note]]`.
19. `skill_view(name="personal-wiki:personal-wiki")` returns bundled `SKILL.md` when the plugin is enabled and fails cleanly when disabled.
20. `hermes plugins enable personal-wiki` followed by `hermes plugins disable personal-wiki` leaves no unintended residual state beyond the expected config toggle.
21. Audit of a realistic synthetic fixture completes within a hard timeout, e.g. 30 seconds.

### Test commands

```bash
scripts/run_tests.sh tests/plugins/test_personal_wiki_scaffold.py \
  tests/plugins/test_personal_wiki_validator.py \
  tests/plugins/test_personal_wiki_plugin.py \
  tests/hermes_cli/test_personal_wiki_cli.py -q
```

Then run a broader plugin slice:

```bash
scripts/run_tests.sh tests/hermes_cli/test_plugins.py tests/test_plugin_skills.py -q
```

## Testing Against an Existing Private Wiki

This must be read-only first. The concrete private path should be provided locally at test time, not committed into this design.

Phase A — sandbox scaffold:

```bash
TMP=$(mktemp -d)
hermes plugins enable personal-wiki
hermes personal-wiki init "$TMP/demo-wiki" --title "Demo Personal Wiki"
hermes personal-wiki validate "$TMP/demo-wiki"
```

Phase B0 — inventory-only plan:

```bash
hermes personal-wiki audit "$PRIVATE_PERSONAL_WIKI_PATH" --plan
```

Review the inventory/skip list before content inspection.

Phase B — read-only audit of the real private wiki:

```bash
hermes personal-wiki audit "$PRIVATE_PERSONAL_WIKI_PATH" --json > /tmp/personal-wiki-audit.json
hermes personal-wiki validate "$PRIVATE_PERSONAL_WIKI_PATH"
```

Expected result for a real private wiki:

- It may have local/private pages and extra structure; that should not fail generic validation.
- It should pass core structural checks or produce explainable warnings.
- Audit should identify reusable improvements without exporting private content.
- Audit outputs written under `/tmp` or another local scratch path should not be committed by default.

Phase C — adoption diff only:

If we add an `adopt` or `upgrade` command later, it must initially be dry-run-only:

```bash
hermes personal-wiki adopt "$PRIVATE_PERSONAL_WIKI_PATH" --dry-run
```

No write-mode adoption until the dry-run diff is reviewed.

## Parking / Pause Plan After Test

After the first successful test on a private wiki:

1. Keep plugin disabled by default for all users.
2. Keep any adoption/upgrade command read-only or dry-run-only until approved.
3. Record findings in the private wiki project page as high-level orientation only.
4. If the plugin works but is not ready to share, mark it as parked/paused with:
   - green scaffold test;
   - green validator test;
   - known warnings from the private-wiki audit;
   - explicit list of remaining blockers before sharing with other people.

## Implementation Plan

### Task 1: Add plugin skeleton

**Files:**

- Create: `plugins/personal-wiki/plugin.yaml`
- Create: `plugins/personal-wiki/__init__.py`
- Create: `plugins/personal-wiki/README.md`
- Create: `plugins/personal-wiki/SKILL.md`

**Verification:** plugin discovery can load it when enabled; the namespaced skill is registered.

### Task 2: Add template renderer and neutral templates

**Files:**

- Create: `plugins/personal-wiki/scaffold.py`
- Create: `plugins/personal-wiki/templates/...`

**Verification:** rendered files contain no forbidden export strings from the optional local denylist and no unresolved variables.

### Task 3: Add generic validator

**Files:**

- Create: `plugins/personal-wiki/validator.py`

**Verification:** temp starter vault passes; intentionally broken fixtures fail with precise messages.

### Task 4: Add CLI command

**Files:**

- Create: `plugins/personal-wiki/cli.py`
- Modify: plugin registration in `__init__.py`

**Verification:** parser tests cover `init`, `validate`, `audit`, `doctor`, `render-template`.

### Task 5: Add sanitization tests

**Files:**

- Create: `plugins/personal-wiki/sanitize.py`
- Create/modify: plugin tests

**Verification:** shipped plugin files/templates cannot include strings from an optional local denylist supplied outside the repository.

### Task 6: Test against a private wiki read-only

**Files:** none expected.

**Verification:** run scaffold in temp dir, run inventory plan for the private wiki, audit the private wiki, validate the private wiki, and capture results in a local report that is not committed by default.

### Task 7: Decide share readiness

**Files:** optional private wiki/project note update.

Classify outcome:

- ready to share;
- shareable after small fixes;
- parked/paused because scaffold works but audit/adoption is not safe enough.

## Open Questions

- Should v1 ship bundled inside Hermes or live first as a user/private plugin tap?
- Should the default starter vault include `.obsidian/` settings or keep Obsidian setup documented only?
- Should `validate` be strict enough to fail on broken wikilinks, or warning-only for early personal vaults?
- Should feedback submissions be a file template only, or a future command like `hermes personal-wiki feedback export`?
- Should `doctor` perform only plan-level checks by default or ask for explicit confirmation before content-level audit?

## Recommendation

Start as a bundled-but-disabled plugin on a branch if the goal is to make it easy for trusted users/agents to test from Hermes. If we want slower/private incubation, start as a user plugin and promote to bundled once the read-only audit is clean.

Safest route:

1. implement as bundled disabled plugin on a branch;
2. test scaffold in `/tmp`;
3. run inventory-only audit plan against the private wiki;
4. run read-only audit/validation after inventory is acceptable;
5. fix obvious generic issues;
6. keep disabled by default and mark parked until sharing policy is decided.

# PLAN-009 / MIS-66 — Read-only profile skill-diet capability matrix and staged proposal

Status: read-only Option B artifact, not implementation approval
Kanban task: `mister-mission-control/t_f089ec8c`
Linear issue: `MIS-66`
Generated: 2026-05-24T21:50:27Z
Artifact owner: `mcplanner`

## Guardrail

This artifact does not approve skill deletion, disablement, moving, or profile persona edits.

Mário's “faz esses que faltam” is treated as approval only for the non-destructive Option B: inspect current capability state and propose a staged allowlist/removal plan. Any actual profile mutation still needs a separate explicit owner approval and a scoped implementation/review card.

## Evidence inspected

- Decision packet: `mister-decisions/t_48f72e29` and source owner-packet task `mister-mission-control/t_7d23cc80`.
- Preserved parent audit evidence: `/home/mister/.hermes/kanban/boards/mister-mission-control/logs/t_b4723dd0.log` lines 39-110.
- Current live profile skill directories:
  - `default`: `/home/mister/.hermes/skills`
  - named profiles: `/home/mister/.hermes/profiles/<profile>/skills`
- Current live profile personas: `/home/mister/.hermes/profiles/<profile>/SOUL.md` where present.
- Current metadata-only cron footprint: `/home/mister/.hermes/profiles/<profile>/cron/*` file names/sizes only; no secret values read.
- Current Kanban board usage via read-only SQLite opens against `~/.hermes/kanban/boards/*/kanban.db`.

No `.env` files, credential stores, secret values, private tokens, or raw credential-bearing logs were read.

## Executive summary

1. The two concrete missing-skill gaps from the earlier audit appear to be remediated now: `linearops` has `mister-programming-agents`; `mcsecurity` has `kdoc-steward`.
2. Capability sprawl remains: all 17 active profiles still carry broad bundles of roughly 90-108 skills, including skills that are not role-required and have high/noisy blast radius for specialized workers.
3. The highest-risk pattern is not one single profile; it is that specialized non-gateway workers all inherit personal-device, messaging/social, smart-home/media, and red-team capability skills that their SOUL/persona does not appear to require.
4. The safest path is a staged allowlist model: first publish per-profile required/optional/owner-gated skill classes, then run dry-run diffs and smoke tests, then ask Mário to approve a specific removal batch.
5. The `mister` gateway/profile should not be included in the first reduction batch because it has 40 cron/state files and broader operational responsibilities; treat it as a separate owner decision after worker profiles are safe.

## Classification vocabulary

- Required: needed for the profile's explicit role, SOUL instructions, Kanban lifecycle, programming-agent routing, Mission Control product direction, or known board responsibilities.
- Optional: useful adjacent capability that may be legitimate for the profile, but should stay only if referenced by role, recent tasks, or owner preference.
- Candidate-remove: installed broadly, not required by role/SOUL, not evidenced by profile board usage, and likely to add noise or blast radius.
- Owner-gated / forbidden-by-default: should not be present on specialized non-gateway workers unless Mário explicitly approves that profile to use it.
- Unknown: insufficient evidence; keep until usage can be checked by session/task history or a dry-run allowlist diff.

## Cross-profile owner-gated skill groups

These groups appear broadly installed and should be owner-gated for specialized non-gateway worker profiles. They are not automatically forbidden for the `mister` gateway/default/general profiles; those need separate review.

| Group | Skill examples observed | Why owner-gated for workers | Default proposal |
|---|---|---|---|
| Red-team/jailbreak | `godmode` | High-risk behavior unrelated to normal planner/spec/backend/QA/KDoc work. | Remove from specialized non-security/red-team workers after approval; keep only where explicitly required. |
| Personal-device / private app surfaces | `apple-notes`, `imessage`, `findmy` | Private-data and personal-device blast radius; almost never needed by role workers. | Owner-gated; candidate-remove from Mission Control worker profiles. |
| Smart-home / physical-world controls | `openhue` | Physical/environmental side effects and distraction risk. | Owner-gated; candidate-remove from all non-smart-home profiles. |
| Social/posting/messaging platforms | `xurl`, `yuanbao`, broad chat/platform skills where installed | External publishing or conversation side effects. | Keep only in gateway/social-specific profiles; remove from backend/spec/QA/planner profiles after approval. |
| Productivity external write APIs | `airtable`, `google-workspace`, `notion`, `himalaya` | Can mutate external SaaS or expose private context if loaded unnecessarily. | Optional only for profiles with explicit workflow need; otherwise candidate-remove. |
| Media/gaming/creative heavy tools | `comfyui`, `heartmula`, `touchdesigner-mcp`, `minecraft-modpack-server`, `pokemon-player`, `spotify` | Large/noisy tool context and unrelated actions. | Candidate-remove from Mission Control workers unless role explicitly needs creative/media/gaming. |
| Research/market niche tools | `polymarket`, `maps` | Usually unrelated to profile role; can distract routing. | Optional/unknown; remove only after task-history dry run shows no use. |

## Profile capability matrix

| Profile | Current skill count | Required allowlist seed | Optional / role-adjacent | Candidate-remove / owner-gated focus | Cron / board evidence | Recommendation |
|---|---:|---|---|---|---|---|
| `default` | 90 | `hermes-agent`, `linear`, `obsidian`, `llm-wiki`, `strategic-accretive-checkpoint` | General-purpose skills; may remain broad if default is intentionally exploratory. | Same broad risky/noisy bundle: `godmode`, Apple/iMessage/FindMy/OpenHue, social/media/gaming/productivity APIs. | No profile cron files found. | Do not start first reduction here; decide whether default is general-purpose or should mirror Mister routing. |
| `linearops` | 92 | `linear`, `hermes-agent`, `mister-programming-agents`, `strategic-accretive-checkpoint` | Kanban/owner-decision skills if it routes blocked Linear work. | Personal-device/social/smart-home/media/gaming skills. | Used on `mister-mission-control` (15 tasks) plus small plugin/review boards; no cron files. | Good early candidate for a strict allowlist after smoke tests. |
| `mcbackend` | 96 | `kanban-worker`, `mister-programming-agents`, `mission-control-product-direction`, `strategic-accretive-checkpoint`, testing/debug/review skills | GitHub/code review, TDD, debugging, security-review support. | Personal-device/social/smart-home/media/gaming and non-backend SaaS write skills. | Heavy board use across Mission Control, improvements, plugins, AVShop; no cron files. | Early candidate, but preserve broad code/test/review skills until task-history dry run. |
| `mcdevorchestrator` | 99 | `kanban-orchestrator`, `mister-programming-agents`, `mission-control-product-direction`, `strategic-accretive-checkpoint`, `owner-decision-packets`, `future-work-kanban` | Linear, KDoc/governance, project/wiki boundary skills. | Personal-device/social/smart-home/media/gaming; red-team. | Heavy Mission Control and improvement board use; no cron files. | Keep orchestration/governance rich; remove obvious unrelated personal/media skills only after approval. |
| `mckanban` | 99 | `kanban-worker`, `mission-control-kanban-manager`, `future-work-kanban`, `owner-decision-packets`, `linear`, `strategic-accretive-checkpoint`, `mister-programming-agents` | Mission Control product direction, Linear routing, Kanban QA/triage helpers. | Personal-device/social/smart-home/media/gaming; red-team. | Active on Mission Control and improvement boards; no cron files. | Do not narrow until Kanban manager/preload workflows are confirmed; then candidate for a moderate allowlist. |
| `mckdoc` | 102 | `kdoc-steward`, `project-documentation-governance`, project-wiki skills, `mission-control-product-direction`, `mister-programming-agents`, `strategic-accretive-checkpoint` | Wiki/review/documentation skills. | Personal-device/social/smart-home/media/gaming; red-team. | Moderate Mission Control/KDoc board use; no cron files. | Keep documentation stack; candidate-remove unrelated personal/media/social skills. |
| `mcplanner` | 97 | `writing-plans`, `plan`, `mister-programming-agents`, `mission-control-product-direction`, `strategic-accretive-checkpoint`, `owner-decision-packets`, `future-work-kanban` | Testing/review/security advisory skills for planning acceptance gates. | Personal-device/social/smart-home/media/gaming; red-team. | Plan/spec tasks on Mission Control/AVShop; no cron files. | Good first canary for a planner allowlist because output is artifact-only and easy to validate. |
| `mcqa` | 99 | `test-driven-development`, `requesting-code-review`, `github-code-review`, `mission-control-product-direction`, `mister-programming-agents`, `strategic-accretive-checkpoint` | Browser/dogfood, security review, KDoc review where explicitly needed. | Personal-device/social/smart-home/media/gaming; red-team unless security test explicitly requires. | Heavy QA board use; no cron files. | Keep QA/browser/review capability; remove unrelated private/device/media skills after approval. |
| `mcsecurity` | 99 | `requesting-code-review`, `github-code-review`, `kdoc-steward`, `project-documentation-governance`, `mister-programming-agents`, `mission-control-product-direction`, `strategic-accretive-checkpoint` | Red-team skill only if Mário explicitly wants this profile to use it; otherwise keep security-review conventional. | Personal-device/smart-home/media/gaming; `godmode` should be explicit owner-gated even here. | Heavy security board use; no cron files. | Do not assume `godmode` is allowed just because profile is security; make red-team scope explicit. |
| `mcspec` | 98 | `writing-plans`, `mission-control-product-direction`, `mister-programming-agents`, `strategic-accretive-checkpoint`, `owner-decision-packets`, `future-work-kanban` | Product/docs/governance and spec review skills. | Personal-device/social/smart-home/media/gaming; red-team. | Spec tasks on Mission Control/plugins/AVShop; no cron files. | Strong early candidate for strict artifact-focused allowlist. |
| `mcspike` | 96 | `spike`, `systematic-debugging`, `mister-programming-agents`, `mission-control-product-direction`, `strategic-accretive-checkpoint` | Domain-specific skills may be attached per spike, not permanently broad. | Personal-device/social/smart-home/media/gaming; red-team by default. | Low current board use; no cron files. | Convert to lean baseline plus per-card skills; good staged canary. |
| `mcui` | 95 | `mission-control-product-direction`, UI/design skills (`popular-web-designs`, `sketch`, `claude-design`), `mister-programming-agents`, `strategic-accretive-checkpoint` | Browser/dogfood, screenshot/QA skills. | Personal-device/social/smart-home/media/gaming; red-team; backend-only skills if unused. | Mission Control UI tasks; no cron files. | Keep product/UI stack; remove unrelated personal/device/media skills after approval. |
| `mister` | 108 | Gateway/orchestration broad set: MPA, Mission Control, strategic, Linear, wiki/KDoc, Hermes Agent, owner-decision/future-work | Many wider skills may be legitimate because this is the main/gateway/operator profile. | Still contains noisy high-blast-radius skills, but not safe to shrink in first wave. | 40 cron/state files; active on capture/review boards. | Exclude from first worker skill diet; separate owner decision with cron/job audit first. |
| `projectwikicurator` | 99 | Project-wiki skill set, KDoc/governance, `mister-programming-agents`, `strategic-accretive-checkpoint` | Sanitized wiki boundary/submission skills. | Personal-device/social/smart-home/media/gaming; private personal wiki write skills unless explicitly approved. | Low Mission Control board use; no cron files. | Candidate for strict project-wiki-only allowlist; do not grant personal wiki canonical update authority. |
| `ram27wiki` | 90 | `obsidian`, `llm-wiki`, `linear`, `strategic-accretive-checkpoint` | RAM 27 wiki curation skill if later created. | Mission Control worker skills not needed; personal wiki direct write skills unless explicitly approved; personal-device/social/media. | Low Mission Control board use; no cron files. | Keep separate from private personal wiki; shrink to RAM27 curation stack only after approval. |
| `wiki` | 92 | `mg-personal-wiki`, `obsidian`, `llm-wiki`, `mister-programming-agents`, `strategic-accretive-checkpoint` | Linear for intake/status; Hermes Agent for profile config questions. | Mission Control implementation skills, personal-device/social/smart-home/media/gaming unless explicitly needed. | Personal-wiki board use; no cron files. | Preserve canonical private wiki authority; remove unrelated operational/action skills only with care. |
| `wikireviewer` | 92 | `mg-personal-wiki`, `obsidian`, `llm-wiki`, `mister-programming-agents`, `strategic-accretive-checkpoint` | Read-only review and boundary-check skills. | Write/action/external-posting/personal-device skills; broad Mission Control coding skills if unused. | Personal-wiki and decision-board review use; no cron files. | Strong candidate for read-only lean allowlist; ensure write tools remain policy-blocked. |

## Proposed staged plan

### Stage 0 — Freeze and approval boundary

Goal: prevent accidental mutation while the matrix is reviewed.

Actions:
- Keep all current skill directories/personas unchanged.
- Treat this artifact as a proposal only.
- Add no deletion/removal implementation cards until Mário explicitly approves a batch.

Validation:
- `git status --short` in `/home/mister/.hermes/hermes-agent` before and after this artifact.
- Confirm only this plan artifact was added/changed by this task.

Rollback:
- Delete only this plan file if Mário rejects the proposal.

### Stage 1 — Snapshot current state before any future mutation

Goal: make any future skill-diet action reversible.

Future implementation task should create a metadata-only backup manifest before editing:
- profile name;
- SOUL path and hash;
- skill directory list and hashes of `SKILL.md` files;
- cron/job file names and hashes where relevant;
- active Kanban boards where profile has tasks;
- explicit owner approval reference.

Do not include secret values, `.env` content, raw private wiki content, or credential-bearing logs.

Recommended backup destination for a future approved task:
- `/home/mister/.hermes/profile-skill-diet-backups/<timestamp>/manifest.json`
- `/home/mister/.hermes/profile-skill-diet-backups/<timestamp>/profiles/<profile>/skills-tree.txt`
- `/home/mister/.hermes/profile-skill-diet-backups/<timestamp>/profiles/<profile>/SOUL.sha256`

Rollback:
- Restore removed skill directories from backup or resync from canonical source profile/repo.
- Restore persona file from backup only if that future task edits it and review approves.

### Stage 2 — Define allowlist files, no removals

Goal: make the policy explicit before touching profile skills.

Proposed future source files, subject to owner approval:
- `docs/profile-skill-diet/allowlists/<profile>.yaml`
- `docs/profile-skill-diet/README.md`

Proposed contract per allowlist:

```yaml
profile: mcplanner
role: Mission Control planner
required:
  - kanban-worker
  - mister-programming-agents
  - mission-control-product-direction
  - strategic-accretive-checkpoint
  - writing-plans
optional:
  - requesting-code-review
  - test-driven-development
owner_gated:
  - godmode
  - apple-notes
  - imessage
  - findmy
  - openhue
candidate_remove:
  - comfyui
  - minecraft-modpack-server
unknown_keep_until_evidence:
  - <skill>
approval_required_for_removal: true
```

Validation:
- YAML parse test.
- Every `required` skill exists in the profile or canonical source.
- Every `candidate_remove` skill exists before proposing removal.
- No unknown skill name typos.

Rollback:
- Remove/revert allowlist files; no profile behavior changes.

### Stage 3 — Dry-run comparator and review packet

Goal: show exactly what would change before any mutation.

Future dry-run output should include:
- per-profile `would_keep`, `would_remove`, `would_add`, `unknown`, and `owner_gated_present` sections;
- whether each removal candidate is referenced in SOUL;
- whether profile has cron jobs;
- whether profile has running/blocked Kanban tasks;
- task-history evidence summary;
- explicit risk label per profile.

Hard blocks for the dry-run:
- profile has active cron jobs and is not explicitly approved for this batch;
- skill is referenced by SOUL or required by injected system persona;
- profile has current running task using the skill;
- removal candidate touches secrets/gateway/auth flow without rollback plan;
- Mário has not approved the exact batch.

Validation:
- Dry-run exits nonzero if it would touch `mister` without separate approval.
- Dry-run exits nonzero if any SOUL-referenced skill is in `would_remove`.
- Dry-run output is a source Markdown/JSON artifact, not a Telegram wall of text.

Rollback:
- No profile changes in dry-run stage.

### Stage 4 — First approved canary removal batch

This stage must not start until Mário approves a specific batch.

Suggested canary profiles:
1. `mcplanner`
2. `mcspec`
3. `mcspike`
4. `wikireviewer`

Reason: these are artifact/review-oriented profiles with no profile-local cron files found and easier smoke validation.

Suggested first candidate-removal group:
- `godmode`
- `apple-notes`
- `imessage`
- `findmy`
- `openhue`
- obvious media/gaming skills not referenced by profile role (`comfyui`, `heartmula`, `touchdesigner-mcp`, `minecraft-modpack-server`, `pokemon-player`, `spotify`)

Required future validation commands/examples:
- `hermes --profile <profile> skill list` or equivalent profile-local skill discovery smoke.
- `hermes --profile <profile> -p "load kanban-worker and report readiness"` with no secrets.
- One minimal Kanban worker dry run or synthetic task per profile if dispatcher supports safe test board.
- Verify no SOUL-required skill was removed.
- Verify no broad profile writes outside the approved profiles.

Rollback:
- Restore exact removed skill directories from Stage 1 backup.
- Re-run profile-local `skill_view` smoke for restored required skills.
- Add Kanban/Linear comment with rollback artifact path.

### Stage 5 — Expand only after canary review

Potential second wave after successful canaries:
- `linearops`
- `mcui`
- `mcqa`
- `mcbackend`
- `mckdoc`
- `projectwikicurator`
- `ram27wiki`
- `wiki`

Profiles requiring extra caution:
- `mckanban` and `mcdevorchestrator`: preserve broad orchestration/board-management skills until work-pack/preload behavior is stable.
- `mcsecurity`: decide explicitly whether red-team skills are allowed; do not infer from the name.
- `mister`: separate owner decision due to cron/gateway/orchestration breadth.
- `default`: separate owner decision because the intended role is unclear/general.

## Task graph for future approved work

```text
T0 Review this matrix with Mário/Mister
  -> T1 Write allowlist YAMLs as proposal-only docs
      -> T2 Build dry-run comparator / report generator
          -> T3 Owner approves exact canary batch
              -> T4 Backup selected profiles
                  -> T5 Apply canary removals
                      -> T6 Smoke tests and Kanban test-board validation
                          -> T7 Review result; decide expand / rollback / stop
```

Dependencies:
- T1 depends on this artifact and owner agreement on classification vocabulary.
- T2 depends on T1 allowlist schemas.
- T3 is an owner decision gate.
- T4-T7 must not run without T3 approval.

## Security gates

- Never read or store `.env`, raw credentials, API keys, tokens, OAuth sessions, private keys, or secret-bearing logs.
- Treat external-write, social-posting, personal-device, smart-home, and red-team skills as owner-gated for specialized non-gateway profiles.
- Keep `mister`/gateway profile outside first wave.
- Do not copy private wiki authority into project/RAM profiles; keep wiki boundaries from existing SOUL instructions.
- Any future script must operate on metadata and hashes unless explicitly reviewing a public skill file.
- Future Linear/Kanban comments must be concise and must not include raw private paths beyond artifact references where necessary.

## QA gates

- Required role skills still load for every modified profile.
- Kanban worker profile startup still receives `kanban-worker` and `mister-programming-agents` where relevant.
- Mission Control product-facing profiles still have `mission-control-product-direction`.
- Planner/spec/doc profiles can still produce artifacts under `docs/plans/` or appropriate project wiki paths.
- Wiki profiles preserve canonical boundaries: `wiki` writes personal wiki; `wikireviewer` reviews; RAM27 stays separate.
- Dry-run and post-change reports are source artifacts, not chat-only summaries.

## Rollback/removal notes

For this task:
- Rollback is simply removing this artifact file if no longer wanted.

For future approved removals:
- Never rely on memory to restore; use Stage 1 backup manifests.
- Remove in small batches by profile, not across all profiles at once.
- Keep removed-skill manifests with hashes.
- Re-run smoke tests immediately after restore.
- If a Kanban worker fails after a diet change, block and restore first; do not stack unrelated debugging onto a capability-removal task.

## Linear/Kanban rollup text

Suggested concise rollup:

```text
MIS-66 Option B read-only matrix complete. Artifact: docs/plans/PLAN-009-mis-66-profile-skill-diet-capability-matrix.md. Current evidence: 17 active profiles still carry 90-108 broad skills; prior missing gaps for linearops/mcsecurity now appear resolved; no profile skills/personas were changed. Recommendation: approve docs-only allowlist + dry-run comparator next, then owner-approved canary removals for mcplanner/mcspec/mcspike/wikireviewer only; keep mister/default/gateway profiles out of first wave.
```

## Strategic checkpoint

- Proposal: Make the next accretive step a docs-only allowlist schema plus dry-run comparator, not removal.
- Evidence: broad bundles remain across all active profiles; the previous concrete gaps are already fixed; `mister` has cron/state responsibilities that make broad removal unsafe.
- Impact: high, because it turns ad-hoc skill cleanup into a reversible profile-governance process.
- Cost: medium.
- Risk: low if kept read-only; medium if merged with actual removals.
- Reversibility: easy through docs-only stage; medium after removals.
- Destination: future Kanban implementation cards only after owner approval.
- Next action: ask Mário/Mister to approve or revise the staged allowlist/dry-run plan before any mutation.

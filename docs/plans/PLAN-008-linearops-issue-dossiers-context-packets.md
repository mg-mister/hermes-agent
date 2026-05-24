# PLAN-008 LinearOps Issue Dossier + Context Packet Implementation Plan

> For Hermes: use the `mister-programming-agents` and `test-driven-development` skills before implementation. This plan is a handoff artifact only; do not implement from the planning worker.

Goal: Ensure every Mister/LinearOps action on a Linear issue is grounded in fresh full Linear context plus a durable per-issue dossier, never only the latest comment/excerpt.

Architecture: Keep Linear as the canonical source. The queue remains a concise redacted trigger stream, while `pending`/`prepare` generate a bounded local Context Packet containing a fresh Linear fetch and a local Issue Dossier stored under Mister's LinearOps state. ACK remains a separate human/handler step and must happen only after the handler verifies the Linear mutation/routing and records dossier evidence.

Tech stack: Python 3 stdlib (`argparse`, `json`, `sqlite3`, `urllib.request`, `pathlib`), Linear GraphQL API, Hermes cron script wrappers, pytest.

---

## Approval and scope gate

Approved source: Linear MIS-85, routed into Kanban task `t_0a9234cf` for planning/spec only.

Implementation scope is limited to these operational artifacts:

- `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- `/home/mister/.hermes/profiles/mister/scripts/linearops.py` (currently identical copy; keep synchronized or choose one canonical script and update wrappers)
- `/home/mister/.hermes/profiles/linearops/scripts/linearops-pending.sh`
- `/home/mister/.hermes/profiles/linearops/scripts/linearops-scan.sh`
- `/home/mister/.hermes/profiles/linearops/scripts/linearops-triage-scan.sh`
- `/home/mister/.hermes/profiles/linearops/scripts/linearops-active-queue.sh`
- `/home/mister/.hermes/profiles/linearops/scripts/linearops_active_manager.py`
- `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_active_manager.py`
- New: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`
- Cron job prompt/script references in `/home/mister/.hermes/profiles/mister/cron/jobs.json` only if a separate cron-change task is approved.

Anti-goals:

- Do not duplicate the entire Linear workspace or make local files canonical.
- Do not create live Hermes sessions for every dormant issue.
- Do not expose private wiki/profile/session context in queue packets.
- Do not store secrets, emails, tokens, env values, or raw secret-bearing Linear text in packets, DB rows, test fixtures, logs, comments, or Kanban handoffs.
- Do not auto-comment, auto-move Linear state, or auto-create Kanban from the scanner/packet generator.

## Current flow observed

1. `linearops-scan.sh` calls `linearops.py scan-comments --limit 120` and appends concise redacted comment handoffs to `/home/mister/.hermes/profiles/mister/linearops/inbox.jsonl`.
2. `linearops-triage-scan.sh` calls `linearops.py scan-triage --limit 120` and appends concise redacted triage handoffs to the same inbox.
3. `linearops-active-queue.sh` calls `linearops_active_manager.py scan --queue --limit 80 --batch-cap 10`; this writes bounded `linear_active_state` queue packets, caps queue writes at 5, dedupes by event/signature, and refuses live Linear/Kanban mutations.
4. `linearops-pending.sh` calls `linearops.py pending --limit 20`; the Mister cron handler `mister-handle-linearops-queue` reads that output every 5 minutes.
5. Existing ACK is file-based via `/home/mister/.hermes/profiles/mister/linearops/acked_comment_ids.txt` and `linearops.py ack <event_key>`.
6. Current `linearops.py` already contains a partial/prototype dossier/context-packet layer: `INTERNAL_DB`, `CONTEXT_PACKET_DIR`, `db_connect()`, `fetch_full_issue_context()`, `normalize_issue_for_packet()`, `build_dossier()`, `prepare_context_packet()`, `attach_context_packet()`, `prepare`, `dossier`, and `status`.
7. Current gap: the new context-packet behavior is not yet covered by dedicated tests, active-manager queue packets do not include `context_packet_path` at creation time, ACK does not enforce/record verified handling, redaction is coarse and needs regression tests, and the cron handler prompt still says “fetch full context” instead of making the packet/dossier contract mandatory.

## Data contracts

### Issue Dossier v1

Storage: SQLite at `/home/mister/.hermes/profiles/mister/linearops/linearops_internal.sqlite3`, table `issue_dossiers`.

The dossier is operational memory, not canonical source. It stores summaries, decisions, open questions, current owner, and last handled event metadata. Raw Linear remains canonical.

Required JSON shape in `issue_dossiers.dossier_json`:

```json
{
  "version": 1,
  "canonical_source": "Linear issue",
  "issue_id": "linear-uuid",
  "identifier": "MIS-85",
  "title": "short title",
  "url": "https://linear.app/...",
  "team": "MIS",
  "project": "Hermes Linear Integration",
  "state": "Mister Review",
  "current_owner": "Mister",
  "assignee": "Name or null",
  "delegate": "Name or null",
  "labels": [{"name": "needs-mister", "parent": "attention"}],
  "session": {
    "session_id": null,
    "session_name": "linear/MIS-85 — short title",
    "policy": "optional continuity aid only; always refetch Linear + dossier before acting"
  },
  "summary": "bounded agent-maintained summary of current issue context",
  "decisions": [],
  "open_questions": [],
  "manual_notes": [],
  "next_steps": [],
  "links": {
    "linear": "https://linear.app/...",
    "attachments": [],
    "documents": [],
    "relations": [],
    "children": [],
    "parent": null,
    "kanban": [],
    "prs": [],
    "wiki": []
  },
  "recent_comment_index": [
    {
      "id": "comment-id",
      "createdAt": "ISO time",
      "user": "display name only",
      "excerpt": "redacted/bounded excerpt",
      "redacted": false
    }
  ],
  "verification_evidence": [
    {
      "event_key": "comment/event key",
      "handled_at": "ISO time",
      "action": "commented|moved-state|created-kanban|no-op",
      "verified_linear_state": "Mister Review",
      "verified_comment_id": "optional comment id",
      "notes": "bounded redacted note"
    }
  ],
  "last_prepared_event_key": "event/comment key",
  "last_acked_event_key": null,
  "last_linear_updated_at": "ISO time",
  "redaction": {
    "policy": "secret-bearing text is replaced with placeholders before local storage or prompts",
    "redacted_fields": []
  },
  "updated_at": "ISO time"
}
```

### Context Packet v1

Storage: JSON files under `/home/mister/.hermes/profiles/mister/linearops/context_packets/` with filenames based on `identifier`, timestamp, and event key.

The packet is the short-lived per-handler work input. It must be readable by Mister before any response, state move, Kanban creation, or ACK.

Required JSON shape:

```json
{
  "version": 1,
  "generated_at": "ISO time",
  "source": "linearops.prepare_context_packet",
  "context_packet_path": "/home/mister/.hermes/profiles/mister/linearops/context_packets/MIS-85__...json",
  "handling_contract": [
    "Linear is canonical; this packet is a bounded fresh fetch plus local dossier.",
    "Do not act only from the queue excerpt or latest comment.",
    "If any content is redacted as secret-bearing, do not copy it into prompts/comments.",
    "After acting, update dossier verification evidence and ACK only after verification."
  ],
  "event": {"kind": "linear_comment|linear_triage_issue|linear_active_state|linear_webhook_event", "event_id": "..."},
  "dossier": {"version": 1, "identifier": "MIS-85"},
  "issue": {
    "id": "linear-uuid",
    "identifier": "MIS-85",
    "title": "...",
    "description": "redacted/bounded markdown",
    "description_redacted": false,
    "description_truncated": false,
    "state": {"name": "Mister Review", "type": "started"},
    "team": {"key": "MIS"},
    "project": {"name": "Hermes Linear Integration"},
    "labels": [],
    "relations": [],
    "attachments": [],
    "documents": [],
    "comments": []
  },
  "context_gaps": [
    "documents were linked but not fetched; inspect Linear document URLs before detailed implementation",
    "redacted secret-bearing content present; manual secret-safe inspection required"
  ],
  "storage": {
    "db_path": "/home/mister/.hermes/profiles/mister/linearops/linearops_internal.sqlite3",
    "context_packet_dir": "/home/mister/.hermes/profiles/mister/linearops/context_packets"
  }
}
```

### Queue item contract

Queue items must remain concise. They may include these packet pointers but not raw full context:

```json
{
  "kind": "linear_active_state",
  "event_id": "active-state:...",
  "issue_identifier": "MIS-85",
  "reason": "bounded redacted reason",
  "redacted_excerpt": "bounded redacted excerpt",
  "context_packet_path": "/home/mister/.hermes/profiles/mister/linearops/context_packets/MIS-85__...json",
  "dossier_db_path": "/home/mister/.hermes/profiles/mister/linearops/linearops_internal.sqlite3",
  "dossier_current_owner": "Mister",
  "handling_contract": "READ context_packet_path before acting; ACK only after verified Linear/dossier update."
}
```

If packet generation fails, `pending` must print `context_packet_error` and a fail-closed instruction: fetch full Linear context manually before acting; do not act from excerpt only.

## Implementation task graph

### Task 1: Freeze the current contract with tests

Objective: Add failing tests that define the dossier/context-packet behavior before touching implementation.

Files:

- Create: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`
- Read-only reference: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`

Steps:

1. Import `linearops.py` with `importlib.util.spec_from_file_location`, mirroring `test_linearops_active_manager.py`.
2. Monkeypatch `linearops.gql` to return a fake full Linear issue with description, comments, labels, relations, attachments, documents, parent, and children.
3. Monkeypatch paths to a temp directory for `QUEUE_DIR`, `QUEUE_FILE`, `ACK_FILE`, `INTERNAL_DB`, and `CONTEXT_PACKET_DIR`.
4. Write tests that `prepare_context_packet({}, issue_ref="MIS-85")` writes one JSON packet and one dossier DB row.
5. Assert packet includes `handling_contract`, `issue`, `dossier`, `context_packet_path`, and no raw secret-looking fixture values.
6. Assert `pending --json` enriches queued items with `context_packet_path`, `dossier_db_path`, `dossier_current_owner`, and the handling contract.
7. Run:

```bash
cd /home/mister/.hermes/profiles/linearops/scripts
python3 -m pytest tests/test_linearops_context_packets.py -q
```

Expected first result: tests fail only where implementation is missing/incomplete.

### Task 2: Harden path configurability and safe test isolation

Objective: Make context packet tests safe without writing production queue/db files.

Files:

- Modify: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- Modify: `/home/mister/.hermes/profiles/mister/scripts/linearops.py` after the canonical copy is green
- Test: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`

Steps:

1. Add a small `Paths` or module-level setter helper only used by tests, or make tests monkeypatch module constants directly.
2. Ensure `write_json()` and DB writes create only the configured temp paths during tests.
3. Add regression assertions that production paths are untouched during tests.
4. Run the context packet tests.

Expected result: tests create files only under `tmp_path`.

### Task 3: Complete dossier and context packet fields

Objective: Fill the required v1 schema without over-collecting private data.

Files:

- Modify: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- Test: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`

Steps:

1. Update `fetch_full_issue_context()` to include only needed Linear fields: issue metadata, labels, assignee/delegate display names, comments, parent/children, relations, attachments, documents.
2. Do not request user emails.
3. Add `context_gaps` to the packet when documents/attachments exist but their content was not fetched, when description/comments are redacted, or when comments are truncated by API limits.
4. Add dossier fields: `summary`, `next_steps`, `verification_evidence`, `last_acked_event_key`, and `redaction` while preserving existing `decisions`, `open_questions`, and `manual_notes` across refreshes.
5. Keep `session_id` optional/null in v1; only create `session_name` mapping.
6. Run:

```bash
cd /home/mister/.hermes/profiles/linearops/scripts
python3 -m pytest tests/test_linearops_context_packets.py -q
```

Expected result: all new schema tests pass.

### Task 4: Enforce redaction boundaries

Objective: Prevent secret-bearing Linear text from entering local packets, queue output, cron prompts, or test logs.

Files:

- Modify: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- Test: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`
- Existing reference: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_active_manager.py`

Steps:

1. Add fixture values that look like `LINEAR_API_KEY=...`, `Authorization: Bearer ...`, emails, query-token URLs, password assignments, and high-entropy strings.
2. Assert packet, dossier JSON, `pending --json`, and printed `pending` output contain placeholders and not the sentinel values.
3. Preserve useful non-secret anti-goals such as “do not touch tokens/secrets” as safe text, matching the active manager's existing anti-goal behavior.
4. Run:

```bash
cd /home/mister/.hermes/profiles/linearops/scripts
python3 -m pytest tests/test_linearops_context_packets.py tests/test_linearops_active_manager.py -q
```

Expected result: redaction and active-manager tests pass.

### Task 5: Wire active-state queue handoffs to packet generation at pending time

Objective: Ensure all queue kinds receive a context packet before the Mister handler sees them.

Files:

- Modify: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- Modify only if needed: `/home/mister/.hermes/profiles/linearops/scripts/linearops_active_manager.py`
- Test: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`
- Existing test: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_active_manager.py`

Steps:

1. Keep active-manager queue packets small; do not embed full context in `linearops_active_manager.py` queue writes.
2. In `linearops.py pending`, call `attach_context_packet()` for every unacked item type: comment, triage, webhook, and active-state.
3. For packet errors, print fail-closed instructions and do not hide the item.
4. Preserve `--json` shape for existing handlers; add fields rather than removing existing ones.
5. Run:

```bash
cd /home/mister/.hermes/profiles/linearops/scripts
python3 -m pytest tests/test_linearops_context_packets.py tests/test_linearops_active_manager.py -q
python3 linearops.py pending --limit 1 --json
```

Expected result: tests pass; live pending command is empty or outputs items with packet pointers and no secret leakage.

### Task 6: Add verified-handoff ACK support

Objective: Make ACK sequencing explicit and auditable without automating Linear decisions.

Files:

- Modify: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- Test: `/home/mister/.hermes/profiles/linearops/scripts/tests/test_linearops_context_packets.py`

Steps:

1. Add optional ACK flags such as:

```bash
python3 linearops.py ack <event_key> --issue MIS-85 --action commented --verified-state "Mister Review" --verified-comment-id <id> --note "bounded redacted note"
```

2. Preserve backward-compatible `linearops.py ack <event_key>` for emergency/manual use, but print a warning that verified flags are preferred.
3. On verified ACK, refresh/fetch dossier, append a bounded `verification_evidence` row, set `last_acked_event_key`, then append the ACK file.
4. If dossier update fails, do not append ACK.
5. Add tests for success sequencing and failure sequencing.
6. Run context packet tests.

Expected result: ACK cannot silently run before dossier evidence in the verified path.

### Task 7: Update Mister handler prompt/runbook contract

Objective: Ensure the cron handler treats `context_packet_path` as mandatory input, not a nice-to-have hint.

Files:

- Review-only first: `/home/mister/.hermes/profiles/mister/cron/jobs.json`
- If approved by Mister: update the `mister-handle-linearops-queue` prompt text and keep `linearops-pending.sh` script unchanged.

Required prompt contract:

- If pending output contains `context_packet_path`, read that packet before any Linear comment/state/Kanban action.
- If pending output contains `context_packet_error`, fetch full Linear context manually before acting.
- Do not ACK from the queue excerpt alone.
- Use verified ACK after Linear state/comment/Kanban routing is checked.
- Keep Linear comments concise; long context stays local in packet/dossier.

Validation command:

```bash
python3 -m json.tool /home/mister/.hermes/profiles/mister/cron/jobs.json >/tmp/linearops-jobs-jsoncheck.out
```

Expected result: JSON remains valid; handler prompt references packet/dossier/verified ACK.

### Task 8: Synchronize canonical script copies

Objective: Avoid drift between the Mister and LinearOps profile script copies.

Files:

- Source: `/home/mister/.hermes/profiles/linearops/scripts/linearops.py`
- Destination: `/home/mister/.hermes/profiles/mister/scripts/linearops.py`

Steps:

1. Decide canonical ownership: recommended canonical source is `/home/mister/.hermes/profiles/linearops/scripts/linearops.py` because cron scan scripts run under profile `linearops`.
2. After tests pass, copy/sync the canonical script to the Mister profile copy or replace one copy with a tiny wrapper that execs the canonical script.
3. Verify equality:

```bash
cmp -s /home/mister/.hermes/profiles/linearops/scripts/linearops.py /home/mister/.hermes/profiles/mister/scripts/linearops.py
echo $?
sha256sum /home/mister/.hermes/profiles/linearops/scripts/linearops.py /home/mister/.hermes/profiles/mister/scripts/linearops.py
```

Expected result: `cmp` exit code 0 if copies remain duplicated; otherwise wrappers clearly document the canonical script.

### Task 9: End-to-end dry-run validation

Objective: Prove the workflow works without mutating Linear.

Commands:

```bash
cd /home/mister/.hermes/profiles/linearops/scripts
python3 -m pytest tests/test_linearops_context_packets.py tests/test_linearops_active_manager.py -q
python3 linearops.py status
python3 linearops.py prepare --issue MIS-85
python3 linearops.py dossier MIS-85
python3 linearops.py pending --limit 1
```

Expected result:

- Tests pass.
- `prepare --issue MIS-85` creates a packet and dossier locally only.
- `dossier MIS-85` shows owner/state/session mapping and no raw secrets.
- `pending` either has no items or prints context-packet paths for every item.
- No Linear comments/state changes are made by these validation commands.

Cleanup after validation when run in production paths:

- If validation created only MIS-85 packet/dossier rows for testing and no handler will use them, remove them with a tiny audited cleanup script or keep them as harmless operational dossier only after Mister approves.

## QA gates

- Unit tests for context packet creation, dossier persistence, pending enrichment, verified ACK sequencing, path isolation, and redaction.
- Existing active manager tests still pass.
- `python3 -m json.tool /home/mister/.hermes/profiles/mister/cron/jobs.json` passes after any cron prompt edit.
- `linearops.py pending --json` remains backward-compatible: existing fields remain present; new fields are additive.
- Manual smoke with MIS-85 confirms fresh full Linear context is fetched before local packet creation.

## Security gates

- No GraphQL query requests user emails.
- No raw `.env`, tokens, API keys, bearer strings, cookies, private keys, query-token URLs, or high-entropy secrets are stored or printed.
- Secret-bearing comments/descriptions are replaced with placeholders and listed in `context_gaps`.
- Context packets are local files under Mister profile state, not Telegram/Linear comments.
- Packet and dossier paths are fixed production paths unless tests explicitly monkeypatch to `tmp_path`.
- Queue item maximum remains bounded; active-manager queue item cap remains 16 KiB.
- Verified ACK must update dossier evidence before appending ACK.

## Rollback/removal plan

1. Pause the handler cron job `mister-handle-linearops-queue` if packet generation breaks handler behavior.
2. Revert `linearops.py` to the pre-plan copy in both profiles.
3. Leave `inbox.jsonl` and `acked_comment_ids.txt` intact; they are the queue continuity source.
4. Remove or archive only generated context packet files under `/home/mister/.hermes/profiles/mister/linearops/context_packets/` if they are invalid.
5. If DB schema is bad, move `/home/mister/.hermes/profiles/mister/linearops/linearops_internal.sqlite3` to a timestamped `.bak` file; Linear remains canonical and dossiers can be regenerated.
6. Unpause cron after `linearops.py pending --limit 1` works again.

## Follow-on Kanban chain

1. `mcbackend`: implement Tasks 1-6 in the LinearOps profile scripts using TDD, with no Linear mutations except read-only fetches for manual smoke.
2. `mcsecurity`: review redaction, local storage, GraphQL field selection, ACK sequencing, and prompt leakage risks.
3. `mcqa`: run unit and smoke validation, including empty queue, packet failure, secret fixture, and MIS-85 manual packet preparation.
4. Optional after green implementation/security/QA: `mister` or LinearOps owner updates the cron handler prompt and posts one concise MIS-85 milestone comment.

## Strategic checkpoint

Single accretive addition: require verified ACK metadata as part of the dossier, not just packet generation. Evidence: the current ACK file is append-only and independent of Linear/dossier verification; MIS-85 explicitly requires ACK only after mutation/verification; active-state manager already dedupes queue writes and needs an audit bridge to handler outcomes. Impact is high because it prevents silent loss of Linear events after partial handling. Cost is medium (ACK CLI flags and tests). Risk is low if backward-compatible ACK remains with a warning. Reversibility is easy by falling back to the old ACK append path.

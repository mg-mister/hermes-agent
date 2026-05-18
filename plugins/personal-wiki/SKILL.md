---
name: personal-wiki
description: Bootstrap, validate, and maintain a generic source-first personal wiki.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [personal-wiki, obsidian, knowledge-management, curation]
---

# Personal Wiki

Use this skill when helping a user bootstrap, validate, or maintain a generic personal wiki based on durable notes, source-first curation, projects inside areas, decisions, dashboards, and conservative privacy rules.

## Principles

- Export the method, not any source installation.
- Keep private content in the user's vault; share only sanitized improvements.
- Prefer read-only audit before changing an existing vault.
- Store raw sources separately from curated notes.
- Keep projects inside areas when possible.
- Promote only durable, non-sensitive knowledge into curated notes.
- Treat secrets, credentials, tokens, phone numbers, and private operational identifiers as non-exportable.

## Folder Model

- `00 System/`: schema, index, log, dashboards.
- `01 Inbox/`: quick captures and drafts awaiting curation.
- `02 Raw/`: raw sources with provenance.
- `10 Areas/`: ongoing life/work domains and their projects.
- `20 Resources/`: reusable references and systems.
- `30 Decisions/`: accepted decisions with rationale.
- `40 Reviews/`: periodic reviews and audits.
- `50 Queries/`: saved views and questions.
- `99 Archive/`: inactive material kept for history.

## CLI

```bash
hermes personal-wiki init PATH --title "Personal Wiki"
hermes personal-wiki audit PATH --plan
hermes personal-wiki audit PATH --json
hermes personal-wiki validate PATH
hermes personal-wiki doctor PATH          # plan-only health summary; no content validation
```

Run `audit --plan` before content-level audit on a private vault. Do not enable write-mode adoption unless the user explicitly approves a reviewed diff.

## Sanitized Feedback

When proposing upstream improvements, include structure, rules, templates, or validator lessons. Do not include private names, paths, group names, project names, credentials, raw chats, or private note content.

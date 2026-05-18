---
type: system
status: active
created: {{created_date}}
owner: {{owner_label}}
---
# Personal Wiki Schema

## Required Frontmatter

Every curated Markdown page should include YAML frontmatter with at least:

```yaml
type: resource
status: draft
```

## Allowed Types

- `system`
- `dashboard`
- `inbox`
- `source`
- `area`
- `project`
- `resource`
- `concept`
- `tool`
- `person`
- `decision`
- `review`
- `query`
- `archive`
- `submission`

## Status Values

Suggested values: `draft`, `active`, `open`, `accepted`, `needs-review`, `archived`.

## Curation Rules

- Preserve provenance for raw sources.
- Promote only durable, reusable, non-sensitive content.
- Keep project notes under their area when possible.
- Use decision notes for accepted rules and rationale.

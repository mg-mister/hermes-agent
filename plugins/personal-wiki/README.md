# Personal Wiki Plugin

`personal-wiki` is an opt-in Hermes plugin for bootstrapping and checking a generic Git/Obsidian personal wiki. It exports a method, not anyone's private vault.

## Commands

```bash
hermes personal-wiki init PATH --title "Personal Wiki"
hermes personal-wiki validate PATH
hermes personal-wiki audit PATH --plan
hermes personal-wiki audit PATH --json
hermes personal-wiki doctor PATH          # plan-only health summary; no content validation
hermes personal-wiki render-template area --output area.md
```

## Safety

- Disabled unless explicitly enabled with `hermes plugins enable personal-wiki`.
- No credentials or network access required.
- `audit --plan` lists inventory before content inspection.
- Existing vault inspection is read-only.
- Secret-like findings are redacted in text and JSON output.
- Local/private export denylists are loaded from external files only; no private strings are committed here.

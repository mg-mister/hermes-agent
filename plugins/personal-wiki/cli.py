"""Operator CLI for the personal-wiki plugin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from .scaffold import ScaffoldError, init_vault, render_note_template
from .validator import audit_vault, validate_vault


def _path_invocation_error(path: str) -> bool:
    return not Path(path).exists()


def _has_parse_or_safety_error(payload: dict[str, Any]) -> bool:
    for issue in payload.get("errors", []):
        message = str(issue.get("message") or "")
        if "invalid frontmatter" in message or "unterminated frontmatter" in message:
            return True
    unsafe_skip_reasons = {"symlink_escape", "broken_symlink", "stat_failed", "not_regular", "too_large"}
    for item in payload.get("skipped", []):
        if item.get("reason") in unsafe_skip_reasons:
            return True
    return False


def register_cli(subparser: argparse.ArgumentParser) -> None:
    actions = subparser.add_subparsers(dest="personal_wiki_action")

    init_p = actions.add_parser("init", help="Create a new generic personal wiki scaffold")
    init_p.add_argument("path")
    init_p.add_argument("--title", default="Personal Wiki")
    init_p.add_argument("--owner-label", default="user")
    init_p.add_argument("--dry-run", action="store_true")

    validate_p = actions.add_parser("validate", help="Validate a personal wiki vault")
    validate_p.add_argument("path")
    validate_p.add_argument("--json", action="store_true")
    validate_p.add_argument("--max-file-size", type=int, default=1024 * 1024)

    audit_p = actions.add_parser("audit", help="Read-only audit of a personal wiki vault")
    audit_p.add_argument("path")
    audit_p.add_argument("--json", action="store_true")
    audit_p.add_argument("--plan", action="store_true")
    audit_p.add_argument("--max-file-size", type=int, default=1024 * 1024)

    doctor_p = actions.add_parser("doctor", help="Print a read-only health summary")
    doctor_p.add_argument("path")

    render_p = actions.add_parser("render-template", help="Render a note template")
    render_p.add_argument("name")
    render_p.add_argument("--output", required=True)
    render_p.add_argument("--vars", default="")
    render_p.add_argument("--owner-label", default="user")

    subparser.set_defaults(func=personal_wiki_command)


def _dump_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_validation(payload: dict[str, Any]) -> None:
    if payload["ok"]:
        print("Personal Wiki validation passed.")
    else:
        print("Personal Wiki validation failed.")
    for issue in payload.get("errors", []):
        print(f"ERROR {issue.get('path')}: {issue.get('message')}")
    for issue in payload.get("warnings", []):
        marker = " [redacted]" if issue.get("redacted") else ""
        print(f"WARN {issue.get('path')}: {issue.get('message')}{marker}")
    if payload.get("skipped"):
        print(f"Skipped {len(payload['skipped'])} file(s).")


def _load_vars(path: str) -> dict[str, Any]:
    if not path:
        return {}
    if yaml is None:
        raise ScaffoldError("YAML support is unavailable")
    try:
        data = yaml.safe_load(Path(path).read_text())
    except Exception as exc:
        raise ScaffoldError(f"could not load vars safely: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ScaffoldError("vars file must contain a mapping")
    return data


def personal_wiki_command(args: argparse.Namespace) -> int:
    action = getattr(args, "personal_wiki_action", None)
    if not action:
        print("Usage: hermes personal-wiki {init|validate|audit|doctor|render-template}")
        return 2

    try:
        if action == "init":
            result = init_vault(
                Path(args.path),
                title=args.title,
                owner_label=args.owner_label,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                print(f"DRY RUN: would create {len(result['planned'])} file(s) under {args.path}")
                for item in result["planned"]:
                    print(f"  {item['path']}")
            else:
                print(f"Created {len(result['created'])} file(s) under {args.path}")
            return 0

        if action == "validate":
            if _path_invocation_error(args.path):
                print(f"personal-wiki error: path does not exist: {args.path}")
                return 2
            payload = validate_vault(Path(args.path), max_file_size=args.max_file_size)
            if getattr(args, "json", False):
                _dump_json(payload)
            else:
                _print_validation(payload)
            if _has_parse_or_safety_error(payload):
                return 2
            return 0 if payload["ok"] else 1

        if action == "audit":
            if _path_invocation_error(args.path):
                print(f"personal-wiki error: path does not exist: {args.path}")
                return 2
            payload = audit_vault(Path(args.path), plan=args.plan, max_file_size=args.max_file_size)
            if getattr(args, "json", False):
                _dump_json(payload)
            elif args.plan:
                print(f"Audit plan: {len(payload['files'])} files considered under {args.path}")
                for item in payload["files"]:
                    print(f"  READ {item['path']}")
                for item in payload.get("skipped", []):
                    print(f"  SKIP {item['path']} ({item['reason']})")
            else:
                counts = payload["counts"]
                print("Personal Wiki audit summary")
                print(f"  files considered: {counts['markdown_files']}")
                print(f"  errors: {counts['validation_errors']}")
                print(f"  warnings: {counts['validation_warnings']}")
                print(f"  skipped: {counts['skipped']}")
            if _has_parse_or_safety_error(payload):
                return 2
            return 0

        if action == "doctor":
            if _path_invocation_error(args.path):
                print(f"personal-wiki error: path does not exist: {args.path}")
                return 2
            plan = audit_vault(Path(args.path), plan=True)
            print("Personal Wiki doctor")
            print(f"  files considered: {len(plan['files'])}")
            print(f"  skipped: {len(plan.get('skipped', []))}")
            print("  content validation: not run")
            print("  next safe action: run `hermes personal-wiki audit PATH --plan` before content audit.")
            return 0

        if action == "render-template":
            variables = _load_vars(args.vars)
            rendered = render_note_template(args.name, owner_label=args.owner_label, variables=variables)
            output = Path(args.output)
            if output.exists():
                raise ScaffoldError(f"output already exists: {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered)
            print(f"Rendered template '{args.name}' to {output}")
            return 0

        print(f"Unknown personal-wiki action: {action}")
        return 2
    except ScaffoldError as exc:
        print(f"personal-wiki error: {exc}")
        return 2

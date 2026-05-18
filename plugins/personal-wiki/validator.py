"""Read-only validator and audit helpers for generic personal wiki vaults."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


DEFAULT_MAX_FILE_SIZE = 1024 * 1024
REQUIRED_DIRS = [
    "00 System",
    "01 Inbox",
    "02 Raw",
    "10 Areas",
    "20 Resources",
    "30 Decisions",
    "40 Reviews",
    "50 Queries",
    "99 Archive",
]
REQUIRED_SYSTEM_FILES = [
    "00 System/SCHEMA.md",
    "00 System/index.md",
    "00 System/log.md",
]
ALLOWED_TYPES = {
    "system",
    "dashboard",
    "inbox",
    "source",
    "area",
    "project",
    "resource",
    "concept",
    "tool",
    "person",
    "decision",
    "review",
    "query",
    "archive",
    "submission",
}
SKIP_DIRS = {
    ".git",
    ".cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
}
SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}")),
    ("generic_secret_assignment", re.compile(r"(?i)(api[_-]?key|password|passwd|token|secret)\s*[:=]")),
    ("private_key", re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----")),
]
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")


def _issue(path: str, message: str, *, line: int | None = None, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"path": path, "message": message, "redacted": False}
    if line is not None:
        item["line"] = line
    item.update(extra)
    return item


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_obsidian_workspace(rel: str) -> bool:
    return rel.startswith(".obsidian/workspace") and rel.endswith(".json")


def _is_hidden_state_dir(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIRS


def iter_safe_markdown_files(
    root: Path | str,
    *,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> tuple[list[Path], list[dict[str, Any]]]:
    root_path = Path(root).resolve()
    skipped: list[dict[str, Any]] = []
    files: list[Path] = []
    if not root_path.exists():
        return files, [_issue(".", "path does not exist", reason="missing_path")]

    for current, dirnames, filenames in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        rel_dir = "." if current_path == root_path else _rel(current_path, root_path)
        for dirname in list(dirnames):
            if _is_hidden_state_dir(dirname):
                skipped.append({
                    "path": _rel(current_path / dirname, root_path),
                    "reason": "hidden_state_dir" if dirname.startswith(".") else "state_dir",
                })
        dirnames[:] = [d for d in dirnames if not _is_hidden_state_dir(d)]
        for filename in filenames:
            path = current_path / filename
            rel = _rel(path, root_path)
            if filename.startswith(".") and filename != ".gitkeep":
                skipped.append({"path": rel, "reason": "hidden_state_file"})
                continue
            if _is_obsidian_workspace(rel):
                skipped.append({"path": rel, "reason": "obsidian_workspace"})
                continue
            try:
                lst = path.lstat()
            except OSError:
                skipped.append({"path": rel, "reason": "stat_failed"})
                continue
            if stat.S_ISLNK(lst.st_mode):
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    skipped.append({"path": rel, "reason": "broken_symlink"})
                    continue
                if not str(resolved).startswith(str(root_path) + os.sep):
                    skipped.append({"path": rel, "reason": "symlink_escape"})
                    continue
            if not path.is_file():
                skipped.append({"path": rel, "reason": "not_regular"})
                continue
            try:
                size = path.stat().st_size
            except OSError:
                skipped.append({"path": rel, "reason": "stat_failed"})
                continue
            if size > max_file_size:
                skipped.append({"path": rel, "reason": "too_large", "size": size})
                continue
            if path.suffix.lower() == ".md":
                files.append(path)
    return sorted(files), skipped


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, str | None]:
    if not text.startswith("---\n"):
        return None, text, None
    try:
        raw, body = text[4:].split("\n---", 1)
    except ValueError:
        return None, text, "unterminated frontmatter"
    if yaml is None:
        return {}, body.lstrip("\n"), None
    try:
        parsed = yaml.safe_load(raw) or {}
    except Exception as exc:
        return None, body.lstrip("\n"), f"invalid frontmatter: {exc.__class__.__name__}"
    if not isinstance(parsed, dict):
        return None, body.lstrip("\n"), "frontmatter must be a mapping"
    return parsed, body.lstrip("\n"), None


def extract_wikilinks(text: str) -> list[str]:
    links: list[str] = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if target.endswith(".md"):
            target = target[:-3]
        if target:
            links.append(target)
    return links


def _note_stems(markdown_files: list[Path], root: Path) -> set[str]:
    stems: set[str] = set()
    for path in markdown_files:
        rel = path.relative_to(root).with_suffix("").as_posix()
        stems.add(rel)
        stems.add(path.stem)
    return stems


def _secret_warnings(path: Path, root: Path, text: str) -> list[dict[str, Any]]:
    rel = _rel(path, root)
    warnings: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                warnings.append({
                    "path": rel,
                    "line": line_no,
                    "kind": kind,
                    "redacted": True,
                    "message": f"secret-like value detected ({kind}); value redacted",
                })
    return warnings


def validate_vault(root: Path | str, *, max_file_size: int = DEFAULT_MAX_FILE_SIZE) -> dict[str, Any]:
    root_path = Path(root).resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    files, skipped = iter_safe_markdown_files(root_path, max_file_size=max_file_size)

    if not root_path.exists():
        errors.append(_issue(".", "path does not exist"))
        return {"ok": False, "errors": errors, "warnings": warnings, "skipped": skipped}

    for rel_dir in REQUIRED_DIRS:
        if not (root_path / rel_dir).exists():
            warnings.append(_issue(rel_dir, "recommended directory is missing"))
    for rel_file in REQUIRED_SYSTEM_FILES:
        if not (root_path / rel_file).exists():
            warnings.append(_issue(rel_file, "recommended system file is missing"))

    known = _note_stems(files, root_path)
    for path in files:
        rel = _rel(path, root_path)
        text = path.read_text(errors="replace")
        warnings.extend(_secret_warnings(path, root_path, text))
        frontmatter, body, fm_error = split_frontmatter(text)
        if fm_error:
            errors.append(_issue(rel, fm_error))
            body = text
        if frontmatter is None:
            missing_issue = _issue(rel, "missing frontmatter")
            if rel in {"README.md", "AGENTS.md", "WIKI_RULES.md", "00 System/log.md"}:
                warnings.append(missing_issue)
            else:
                errors.append(missing_issue)
            body = text
        else:
            note_type = frontmatter.get("type")
            if note_type not in ALLOWED_TYPES:
                errors.append(_issue(rel, f"invalid type: {note_type!r}"))
            if frontmatter.get("type") == "project":
                for heading in ["## Outcome", "## Current State", "## Next Actions"]:
                    if heading not in body:
                        warnings.append(_issue(rel, f"project page missing section: {heading}"))
        for target in extract_wikilinks(body):
            if target not in known:
                warnings.append(_issue(
                    rel,
                    "broken wikilink target redacted",
                    kind="broken_wikilink",
                    redacted=True,
                ))

    return {"ok": not errors, "errors": errors, "warnings": warnings, "skipped": skipped}


def audit_vault(
    root: Path | str,
    *,
    plan: bool = False,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    files, skipped = iter_safe_markdown_files(root_path, max_file_size=max_file_size)
    inventory = [{"path": _rel(path, root_path), "size": path.stat().st_size} for path in files]
    if plan:
        return {"mode": "plan", "root": ".", "files": inventory, "skipped": skipped}

    validation = validate_vault(root_path, max_file_size=max_file_size)
    counts = {
        "markdown_files": len(files),
        "validation_errors": len(validation["errors"]),
        "validation_warnings": len(validation["warnings"]),
        "skipped": len(skipped),
    }
    needs_review: list[dict[str, str]] = []
    empty_placeholders: list[dict[str, str]] = []
    for path in files:
        text = path.read_text(errors="replace")
        rel = _rel(path, root_path)
        if "needs-review" in text:
            needs_review.append({"path": rel})
        if text.strip().endswith("TODO") or "Add durable" in text:
            empty_placeholders.append({"path": rel})
    return {
        "mode": "audit",
        "root": ".",
        "counts": counts,
        "warnings": validation["warnings"],
        "errors": validation["errors"],
        "skipped": skipped,
        "needs_review": needs_review,
        "empty_placeholders": empty_placeholders,
    }

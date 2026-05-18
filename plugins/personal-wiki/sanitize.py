"""Sanitization helpers for exportable personal-wiki plugin assets."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


FORBIDDEN_EXPORT_STRINGS: list[str] = []


def load_denylist(path: Path | str | None) -> list[str]:
    if not path:
        return []
    denylist_path = Path(path)
    if not denylist_path.exists():
        return []
    patterns: list[str] = []
    for line in denylist_path.read_text().splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        patterns.append(item)
    return patterns


def _all_patterns(patterns: Iterable[str] = ()) -> list[str]:
    return list(FORBIDDEN_EXPORT_STRINGS) + list(patterns)


def check_export_text(text: str, *, patterns: Iterable[str] = ()) -> list[str]:
    findings: list[str] = []
    for pattern in _all_patterns(patterns):
        if pattern and pattern in text:
            findings.append(pattern)
    return findings


def iter_export_findings(text: str, *, patterns: Iterable[str] = ()) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for index, pattern in enumerate(_all_patterns(patterns)):
        if pattern and pattern in text:
            findings.append({"pattern_index": index, "redacted": True})
    return findings


def check_export_files(
    paths: Iterable[Path | str],
    *,
    denylist_path: Path | str | None = None,
) -> list[dict[str, object]]:
    patterns = load_denylist(denylist_path)
    findings: list[dict[str, object]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(errors="replace")
        for finding in iter_export_findings(text, patterns=patterns):
            findings.append({"path": str(path), **finding})
    return findings

"""Scaffold rendering for the personal-wiki plugin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Template
from typing import Iterable


PLUGIN_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PLUGIN_DIR / "templates"
VAULT_TEMPLATES_DIR = TEMPLATES_DIR / "vault"
NOTE_TEMPLATES_DIR = TEMPLATES_DIR / "notes"


class ScaffoldError(RuntimeError):
    """Raised when scaffold creation would be unsafe."""


@dataclass(frozen=True)
class PlannedFile:
    path: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "content": self.content}


def _vars(
    *,
    title: str = "Personal Wiki",
    owner_label: str = "user",
    created_date: str | None = None,
) -> dict[str, str]:
    return {
        "vault_title": title or "Personal Wiki",
        "owner_label": owner_label or "user",
        "created_date": created_date or date.today().isoformat(),
    }


def _render_text(text: str, variables: dict[str, str]) -> str:
    rendered = text
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    if "{{" in rendered or "}}" in rendered:
        raise ScaffoldError("unresolved template placeholder")
    return rendered


def _iter_template_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def plan_vault(
    target: Path | str,
    *,
    title: str = "Personal Wiki",
    owner_label: str = "user",
    created_date: str | None = None,
) -> list[PlannedFile]:
    del target  # target is part of the public API; paths are relative.
    variables = _vars(title=title, owner_label=owner_label, created_date=created_date)
    planned: list[PlannedFile] = []
    for source in _iter_template_files(VAULT_TEMPLATES_DIR):
        rel = source.relative_to(VAULT_TEMPLATES_DIR).as_posix()
        text = source.read_text()
        planned.append(PlannedFile(path=rel, content=_render_text(text, variables)))
    return planned


def init_vault(
    target: Path | str,
    *,
    title: str = "Personal Wiki",
    owner_label: str = "user",
    dry_run: bool = False,
) -> dict:
    target_path = Path(target)
    planned = plan_vault(target_path, title=title, owner_label=owner_label)
    planned_dicts = [{"path": item.path} for item in planned]
    if dry_run:
        return {"dry_run": True, "target": str(target_path), "planned": planned_dicts}

    if target_path.exists() and any(target_path.iterdir()):
        raise ScaffoldError(f"target directory is not empty: {target_path}")

    created: list[str] = []
    target_path.mkdir(parents=True, exist_ok=True)
    for item in planned:
        dest = target_path / item.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item.content)
        created.append(item.path)
    return {"dry_run": False, "target": str(target_path), "created": created}


def render_note_template(
    name: str,
    *,
    title: str | None = None,
    owner_label: str = "user",
    created_date: str | None = None,
    variables: dict | None = None,
) -> str:
    safe_name = name.removesuffix(".md")
    if "/" in safe_name or "\\" in safe_name or safe_name in {"", ".", ".."}:
        raise ScaffoldError("invalid template name")
    path = NOTE_TEMPLATES_DIR / f"{safe_name}.md"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in NOTE_TEMPLATES_DIR.glob("*.md")))
        raise ScaffoldError(f"unknown template '{name}'. Available: {available}")
    data = _vars(title=title or safe_name.title(), owner_label=owner_label, created_date=created_date)
    for key, value in (variables or {}).items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            data[str(key)] = "" if value is None else str(value)
    rendered = _render_text(path.read_text(), data)
    if "{{" in rendered or "}}" in rendered:
        raise ScaffoldError("unresolved template placeholder")
    return rendered

"""Tests for the bundled personal-wiki plugin v0.1."""

from __future__ import annotations

import importlib
import importlib.util
import json
import stat
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins" / "personal-wiki"
PKG_NAME = "test_personal_wiki_plugin"


def _load_pkg():
    if PKG_NAME in sys.modules:
        return sys.modules[PKG_NAME]
    spec = importlib.util.spec_from_file_location(
        PKG_NAME,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = PKG_NAME
    module.__path__ = [str(PLUGIN_DIR)]
    sys.modules[PKG_NAME] = module
    spec.loader.exec_module(module)
    return module


def _mod(name: str):
    _load_pkg()
    return importlib.import_module(f"{PKG_NAME}.{name}")


def test_init_dry_run_writes_nothing(tmp_path):
    scaffold = _mod("scaffold")
    target = tmp_path / "demo-wiki"

    result = scaffold.init_vault(target, title="Demo Personal Wiki", dry_run=True)

    assert result["dry_run"] is True
    assert any(item["path"] == "00 System/SCHEMA.md" for item in result["planned"])
    assert not target.exists()


def test_init_creates_neutral_layout_and_validate_passes(tmp_path):
    scaffold = _mod("scaffold")
    validator = _mod("validator")
    target = tmp_path / "demo-wiki"

    result = scaffold.init_vault(target, title="Demo Personal Wiki", owner_label="user")
    validation = validator.validate_vault(target)

    assert result["created"]
    assert (target / "00 System" / "SCHEMA.md").exists()
    assert (target / "01 Inbox" / "drafts" / ".gitkeep").exists()
    assert validation["ok"] is True
    all_text = "\n".join(p.read_text() for p in target.rglob("*.md"))
    assert "{{" not in all_text
    assert "Mário" not in all_text
    assert "Mister" not in all_text
    assert "RAM 27" not in all_text


def test_init_refuses_non_empty_directory(tmp_path):
    scaffold = _mod("scaffold")
    target = tmp_path / "demo-wiki"
    target.mkdir()
    (target / "keep.txt").write_text("existing")

    with pytest.raises(scaffold.ScaffoldError, match="not empty"):
        scaffold.init_vault(target)


def test_validate_catches_missing_frontmatter_invalid_type_and_broken_wikilink(tmp_path):
    scaffold = _mod("scaffold")
    validator = _mod("validator")
    target = tmp_path / "wiki"
    scaffold.init_vault(target)
    bad = target / "20 Resources" / "bad.md"
    bad.write_text("# Bad\n\nMissing frontmatter and [[No Such Note]].\n")
    wrong = target / "20 Resources" / "wrong.md"
    wrong.write_text("---\ntype: made-up\nstatus: draft\n---\n# Wrong\n")

    result = validator.validate_vault(target)

    assert result["ok"] is False
    messages = "\n".join(issue["message"] for issue in result["errors"] + result["warnings"])
    assert "frontmatter" in messages
    assert "invalid type" in messages
    assert "broken wikilink" in messages


def test_secret_detection_is_redacted_in_text_and_json(tmp_path):
    validator = _mod("validator")
    target = tmp_path / "wiki"
    (target / "20 Resources").mkdir(parents=True)
    token = "ghp_" + ("A" * 32)
    (target / "20 Resources" / "secret.md").write_text(
        f"---\ntype: resource\nstatus: draft\n---\n# Secret\n\ntoken = {token}\n"
    )

    result = validator.validate_vault(target)
    encoded = json.dumps(result)

    assert token not in encoded
    assert any(w.get("redacted") is True for w in result["warnings"])


def test_audit_plan_lists_inventory_without_reading_content(tmp_path):
    validator = _mod("validator")
    target = tmp_path / "wiki"
    target.mkdir()
    secret = "AKIA" + ("A" * 16)
    (target / "note.md").write_text(f"# Note\n{secret}\n")

    result = validator.audit_vault(target, plan=True)

    assert result["mode"] == "plan"
    assert any(item["path"] == "note.md" for item in result["files"])
    assert secret not in json.dumps(result)
    assert result["root"] == "."
    assert str(target) not in json.dumps(result)


@pytest.mark.skipif(sys.platform == "win32", reason="Symlink behavior differs on Windows")
def test_audit_refuses_symlink_that_escapes_root(tmp_path):
    validator = _mod("validator")
    target = tmp_path / "wiki"
    outside = tmp_path / "outside.md"
    target.mkdir()
    outside.write_text("---\ntype: resource\n---\n# Outside\n")
    (target / "escape.md").symlink_to(outside)

    result = validator.audit_vault(target)

    assert any(item["reason"] == "symlink_escape" for item in result["skipped"])


def test_audit_skips_large_files(tmp_path):
    validator = _mod("validator")
    target = tmp_path / "wiki"
    target.mkdir()
    (target / "large.md").write_text("x" * 128)

    result = validator.audit_vault(target, max_file_size=32)

    assert any(item["reason"] == "too_large" for item in result["skipped"])


def test_audit_skips_hidden_state_directories(tmp_path):
    validator = _mod("validator")
    target = tmp_path / "wiki"
    hidden = target / ".obsidian"
    hidden.mkdir(parents=True)
    (hidden / "plugins.json").write_text("{}")

    result = validator.audit_vault(target, plan=True)

    assert any(
        item["path"] == ".obsidian" and item["reason"] == "hidden_state_dir"
        for item in result["skipped"]
    )


def test_broken_wikilink_warning_redacts_private_target(tmp_path):
    validator = _mod("validator")
    target = tmp_path / "wiki"
    target.mkdir()
    private_target = "Private Client Roadmap"
    (target / "note.md").write_text(
        f"---\ntype: resource\nstatus: draft\n---\n# Note\n\n[[{private_target}]]\n"
    )

    result = validator.validate_vault(target)
    encoded = json.dumps(result)

    assert private_target not in encoded
    assert any(
        item.get("kind") == "broken_wikilink" and item.get("redacted") is True
        for item in result["warnings"]
    )


def test_wikilink_parser_handles_alias_heading_folder_and_embeds():
    validator = _mod("validator")
    text = "[[Note#Heading|Alias]] [[Note.md]] [[folder/Note]] ![[Embed]]"

    links = validator.extract_wikilinks(text)

    assert links == ["Note", "Note", "folder/Note", "Embed"]


def test_local_sanitize_denylist_rejects_shipped_text(tmp_path):
    sanitize = _mod("sanitize")
    candidate = tmp_path / "candidate.md"
    denylist = tmp_path / "denylist.local.txt"
    candidate.write_text("This file mentions PrivateProject.")
    denylist.write_text("PrivateProject\n")

    findings = sanitize.check_export_files([candidate], denylist_path=denylist)

    assert findings == [{"path": str(candidate), "pattern_index": 0, "redacted": True}]


def test_plugin_registers_cli_and_namespaced_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    config_path = tmp_path / ".hermes" / "config.yaml"
    config_path.parent.mkdir()
    config_path.write_text(yaml.safe_dump({"plugins": {"enabled": ["personal-wiki"]}}))

    from hermes_cli.plugins import PluginManager

    mgr = PluginManager()
    mgr.discover_and_load(force=True)

    assert "personal-wiki" in mgr._plugins
    assert mgr._plugins["personal-wiki"].enabled is True
    assert "personal-wiki" in mgr._cli_commands
    assert mgr.find_plugin_skill("personal-wiki:personal-wiki") == PLUGIN_DIR / "SKILL.md"


def test_plugin_import_has_no_user_vault_side_effects(tmp_path, monkeypatch):
    marker = tmp_path / "vault" / "unexpected.txt"
    monkeypatch.setenv("PERSONAL_WIKI_PATH", str(marker.parent))

    _load_pkg()

    assert not marker.exists()

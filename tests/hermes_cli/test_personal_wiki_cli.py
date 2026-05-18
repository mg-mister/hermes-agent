"""CLI tests for the bundled personal-wiki plugin."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins" / "personal-wiki"
PKG_NAME = "test_personal_wiki_cli_plugin"


def _load_cli():
    if PKG_NAME not in sys.modules:
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
    return importlib.import_module(f"{PKG_NAME}.cli")


def _parse(argv: list[str]) -> argparse.Namespace:
    cli = _load_cli()
    parser = argparse.ArgumentParser(prog="hermes personal-wiki")
    cli.register_cli(parser)
    return parser.parse_args(argv)


def test_cli_init_dry_run_prints_plan_and_writes_nothing(tmp_path, capsys):
    cli = _load_cli()
    target = tmp_path / "demo"
    args = _parse(["init", str(target), "--title", "Demo", "--dry-run"])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "DRY RUN" in output
    assert "00 System/SCHEMA.md" in output
    assert not target.exists()


def test_cli_validate_json_redacts_secret(tmp_path, capsys):
    cli = _load_cli()
    target = tmp_path / "wiki"
    (target / "20 Resources").mkdir(parents=True)
    token = "ghp_" + ("A" * 32)
    (target / "20 Resources" / "secret.md").write_text(
        f"---\ntype: resource\nstatus: draft\n---\n# Secret\n\n{token}\n"
    )
    args = _parse(["validate", str(target), "--json"])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 0
    assert token not in output
    payload = json.loads(output)
    assert payload["ok"] is True
    assert any(item["redacted"] is True for item in payload["warnings"])


def test_cli_render_template_rejects_unsafe_yaml(tmp_path, capsys):
    cli = _load_cli()
    vars_path = tmp_path / "vars.yaml"
    output_path = tmp_path / "area.md"
    vars_path.write_text("!!python/object/apply:os.system ['echo unsafe']\n")
    args = _parse(["render-template", "area", "--output", str(output_path), "--vars", str(vars_path)])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 2
    assert "unsafe" in output.lower() or "could not" in output.lower()
    assert not output_path.exists()


def test_cli_doctor_runs_read_only_summary(tmp_path, capsys):
    cli = _load_cli()
    target = tmp_path / "wiki"
    target.mkdir()
    (target / "note.md").write_text("# Note\n")
    args = _parse(["doctor", str(target)])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "Personal Wiki doctor" in output
    assert "files considered" in output
    assert "content validation: not run" in output


def test_cli_missing_path_returns_invocation_error(tmp_path, capsys):
    cli = _load_cli()
    missing = tmp_path / "missing"
    args = _parse(["validate", str(missing)])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 2
    assert "path does not exist" in output


def test_cli_audit_json_does_not_emit_absolute_root(tmp_path, capsys):
    cli = _load_cli()
    target = tmp_path / "wiki"
    target.mkdir()
    (target / "note.md").write_text("---\ntype: resource\nstatus: draft\n---\n# Note\n")
    args = _parse(["audit", str(target), "--json", "--plan"])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 0
    payload = json.loads(output)
    assert payload["root"] == "."
    assert str(target) not in output


@pytest.mark.skipif(sys.platform == "win32", reason="Symlink behavior differs on Windows")
def test_cli_validate_returns_invocation_error_for_symlink_escape(tmp_path, capsys):
    cli = _load_cli()
    target = tmp_path / "wiki"
    outside = tmp_path / "outside.md"
    target.mkdir()
    outside.write_text("---\ntype: resource\nstatus: draft\n---\n# Outside\n")
    (target / "escape.md").symlink_to(outside)
    args = _parse(["validate", str(target)])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 2
    assert "Skipped" in output


@pytest.mark.skipif(sys.platform == "win32", reason="Symlink behavior differs on Windows")
def test_cli_audit_returns_invocation_error_for_symlink_escape(tmp_path, capsys):
    cli = _load_cli()
    target = tmp_path / "wiki"
    outside = tmp_path / "outside.md"
    target.mkdir()
    outside.write_text("---\ntype: resource\nstatus: draft\n---\n# Outside\n")
    (target / "escape.md").symlink_to(outside)
    args = _parse(["audit", str(target), "--plan"])

    code = cli.personal_wiki_command(args)
    output = capsys.readouterr().out

    assert code == 2
    assert "symlink_escape" in output

"""Generic personal wiki plugin.

Registers a CLI command and bundled skill only. Importing this module does not
inspect user vaults, read environment-specific paths, or write files.
"""

from __future__ import annotations

from pathlib import Path

from .cli import personal_wiki_command, register_cli


def register(ctx) -> None:
    ctx.register_skill(
        "personal-wiki",
        Path(__file__).with_name("SKILL.md"),
        "Bootstrap, validate, and maintain a generic source-first personal wiki.",
    )
    ctx.register_cli_command(
        name="personal-wiki",
        help="Bootstrap and validate a generic personal wiki vault",
        setup_fn=register_cli,
        handler_fn=personal_wiki_command,
        description="Create, audit, and validate a Git/Obsidian personal wiki skeleton.",
    )

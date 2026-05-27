"""Tests for cross-profile auth fallback.

When ``HERMES_HOME`` points to a named profile, ``read_credential_pool()``
and ``get_provider_auth_state()`` fall back to the global-root
``auth.json`` per-provider when the profile has no entries for that
provider.  Writes still target the profile only.

See the #18594 follow-up report: profile workers couldn't see providers
authenticated only at the global root.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time

import pytest


def _make_auth_store(pool: dict | None = None, providers: dict | None = None) -> dict:
    store: dict = {"version": 1}
    if pool is not None:
        store["credential_pool"] = pool
    if providers is not None:
        store["providers"] = providers
    return store


@pytest.fixture()
def profile_env(tmp_path, monkeypatch):
    """Set up a global root + an active profile under Path.home()/.hermes/profiles/coder.

    * Path.home() -> tmp_path
    * Global root -> tmp_path/.hermes            (has its own auth.json fixture)
    * Profile     -> tmp_path/.hermes/profiles/coder   (active, HERMES_HOME points here)

    This mirrors the real "named profile mounted under the default root"
    layout that profile users actually have on disk.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    global_root = tmp_path / ".hermes"
    global_root.mkdir()
    profile_dir = global_root / "profiles" / "coder"
    profile_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile_dir))
    return {"global": global_root, "profile": profile_dir}


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# read_credential_pool — provider-slice reads
# ---------------------------------------------------------------------------


def test_profile_with_zero_entries_falls_back_to_global(profile_env):
    """Empty profile pool inherits the global-root entries for that provider."""
    from hermes_cli.auth import read_credential_pool

    _write(profile_env["global"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "glob-1",
            "label": "global-key",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-global",
        }],
    }))
    # Profile auth.json: exists but has no openrouter entries.
    _write(profile_env["profile"] / "auth.json", _make_auth_store(pool={}))

    entries = read_credential_pool("openrouter")
    assert len(entries) == 1
    assert entries[0]["id"] == "glob-1"
    assert entries[0]["access_token"] == "sk-or-global"


def test_profile_with_entries_fully_shadows_global(profile_env):
    """Once the profile has any entries for a provider, global is ignored."""
    from hermes_cli.auth import read_credential_pool

    _write(profile_env["global"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "glob-1",
            "label": "global-key",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-global",
        }],
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "prof-1",
            "label": "profile-key",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-profile",
        }],
    }))

    entries = read_credential_pool("openrouter")
    assert len(entries) == 1
    assert entries[0]["id"] == "prof-1"
    assert entries[0]["access_token"] == "sk-or-profile"


def test_per_provider_shadowing_is_independent(profile_env):
    """Profile can override one provider while inheriting another from global."""
    from hermes_cli.auth import read_credential_pool

    _write(profile_env["global"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "glob-or",
            "label": "global-or",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-global",
        }],
        "anthropic": [{
            "id": "glob-ant",
            "label": "global-ant",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-ant-global",
        }],
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(pool={
        # Profile has openrouter only — anthropic should still fall back.
        "openrouter": [{
            "id": "prof-or",
            "label": "profile-or",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-profile",
        }],
    }))

    or_entries = read_credential_pool("openrouter")
    ant_entries = read_credential_pool("anthropic")
    assert [e["id"] for e in or_entries] == ["prof-or"]
    assert [e["id"] for e in ant_entries] == ["glob-ant"]


def test_missing_global_auth_file_is_safe(profile_env):
    """Profile processes that never had a global auth.json still work."""
    from hermes_cli.auth import read_credential_pool

    # No global auth.json written at all.
    _write(profile_env["profile"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "prof-1",
            "label": "profile",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-profile",
        }],
    }))

    assert read_credential_pool("openrouter")[0]["id"] == "prof-1"
    assert read_credential_pool("anthropic") == []


def test_malformed_global_auth_file_does_not_break_profile_read(profile_env):
    (profile_env["global"] / "auth.json").write_text("{not valid json")
    _write(profile_env["profile"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "prof-1",
            "label": "profile",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-profile",
        }],
    }))

    from hermes_cli.auth import read_credential_pool

    # Profile reads still work; malformed global is silently ignored.
    assert read_credential_pool("openrouter")[0]["id"] == "prof-1"
    # And no fallback for anthropic since global is unreadable.
    assert read_credential_pool("anthropic") == []


# ---------------------------------------------------------------------------
# read_credential_pool — whole-pool reads (provider_id=None)
# ---------------------------------------------------------------------------


def test_whole_pool_merges_global_providers_when_missing_locally(profile_env):
    from hermes_cli.auth import read_credential_pool

    _write(profile_env["global"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "glob-or",
            "label": "global-or",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-global",
        }],
        "anthropic": [{
            "id": "glob-ant",
            "label": "global-ant",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-ant-global",
        }],
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "prof-or",
            "label": "profile-or",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-or-profile",
        }],
    }))

    pool = read_credential_pool(None)
    # Profile wins for openrouter, global fills in anthropic.
    assert [e["id"] for e in pool["openrouter"]] == ["prof-or"]
    assert [e["id"] for e in pool["anthropic"]] == ["glob-ant"]


# ---------------------------------------------------------------------------
# get_provider_auth_state — singleton fallback
# ---------------------------------------------------------------------------


def test_provider_auth_state_falls_back_to_global_when_profile_has_none(profile_env):
    from hermes_cli.auth import get_provider_auth_state

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "nous": {"access_token": "nous-global", "refresh_token": "rt-global"},
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={}))

    state = get_provider_auth_state("nous")
    assert state is not None
    assert state["access_token"] == "nous-global"


def test_provider_auth_state_profile_wins_when_present(profile_env):
    from hermes_cli.auth import get_provider_auth_state

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "nous": {"access_token": "nous-global"},
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={
        "nous": {"access_token": "nous-profile"},
    }))

    state = get_provider_auth_state("nous")
    assert state is not None
    assert state["access_token"] == "nous-profile"


def test_provider_auth_state_returns_none_when_neither_has_it(profile_env):
    from hermes_cli.auth import get_provider_auth_state

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={}))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={}))

    assert get_provider_auth_state("nous") is None


# ---------------------------------------------------------------------------
# Classic mode — no fallback path should ever trigger
# ---------------------------------------------------------------------------


def test_classic_mode_does_not_double_read_same_file(tmp_path, monkeypatch):
    """In classic mode (HERMES_HOME == global root), no fallback path runs.

    This guards against the merge accidentally duplicating entries when the
    profile and global resolve to the same directory.
    """
    # Put Path.home() under a subdir so the seat belt in _auth_file_path()
    # sees tmp_path/home/.hermes as the "real home" — which is NOT equal
    # to the HERMES_HOME we set (tmp_path/classic), so the guard passes.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    hermes_home = tmp_path / "classic"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    _write(hermes_home / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "only",
            "label": "classic",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-classic",
        }],
    }))

    from hermes_cli.auth import read_credential_pool, _global_auth_file_path

    # Classic mode: HERMES_HOME is set to a custom path that is NOT under
    # ~/.hermes/profiles/ — get_default_hermes_root() returns HERMES_HOME
    # itself, so the profile root and global root are the same directory,
    # and the helper correctly returns None (no fallback).
    assert _global_auth_file_path() is None
    # And the read should return exactly one entry (not two).
    entries = read_credential_pool("openrouter")
    assert len(entries) == 1
    assert entries[0]["id"] == "only"


# ---------------------------------------------------------------------------
# Writes stay scoped to the profile
# ---------------------------------------------------------------------------


def test_write_credential_pool_targets_profile_not_global(profile_env):
    from hermes_cli.auth import read_credential_pool, write_credential_pool

    _write(profile_env["global"] / "auth.json", _make_auth_store(pool={
        "openrouter": [{
            "id": "glob-1",
            "label": "global",
            "auth_type": "api_key",
            "priority": 0,
            "source": "manual",
            "access_token": "sk-global",
        }],
    }))

    write_credential_pool("openrouter", [{
        "id": "prof-new",
        "label": "profile-new",
        "auth_type": "api_key",
        "priority": 0,
        "source": "manual",
        "access_token": "***",
    }])

    # Global auth.json unchanged.
    global_data = json.loads((profile_env["global"] / "auth.json").read_text())
    assert global_data["credential_pool"]["openrouter"][0]["id"] == "glob-1"

    # Profile auth.json holds the new entry.
    profile_data = json.loads((profile_env["profile"] / "auth.json").read_text())
    assert profile_data["credential_pool"]["openrouter"][0]["id"] == "prof-new"

    # Subsequent read returns profile (shadows global).
    assert [e["id"] for e in read_credential_pool("openrouter")] == ["prof-new"]


# ---------------------------------------------------------------------------
# OpenAI Codex profile workers — global auth broker fallback
# ---------------------------------------------------------------------------


def _codex_state(access_token: str = "access", refresh_token: str = "refresh") -> dict:
    return {
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        "auth_mode": "chatgpt",
        "last_refresh": "2026-01-01T00:00:00Z",
    }


def _jwt_with_exp(exp: int) -> str:
    def encode(payload: bytes) -> str:
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")

    return ".".join([
        encode(b'{"alg":"none"}'),
        encode(json.dumps({"exp": exp}).encode("utf-8")),
        "signature",
    ])


def test_codex_runtime_falls_back_to_global_when_profile_has_no_local_state(profile_env):
    from hermes_cli.auth import resolve_codex_runtime_credentials

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state("global-access", "global-refresh"),
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={}))

    creds = resolve_codex_runtime_credentials(refresh_if_expiring=False)

    assert creds["api_key"] == "global-access"
    assert creds["source"] == "hermes-global-auth-store"
    assert creds["auth_store"] == str(profile_env["global"] / "auth.json")


def test_codex_runtime_ignores_stale_profile_state_when_global_is_healthy(profile_env):
    from hermes_cli.auth import resolve_codex_runtime_credentials

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state("global-access", "global-refresh"),
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={
        "openai-codex": {
            "tokens": {"access_token": "", "refresh_token": ""},
            "last_auth_error": {"code": "refresh_token_reused"},
        },
    }))

    creds = resolve_codex_runtime_credentials(refresh_if_expiring=False)

    assert creds["api_key"] == "global-access"
    assert creds["source"] == "hermes-global-auth-store"


def test_codex_runtime_prefers_global_even_when_profile_has_local_state(profile_env):
    from hermes_cli.auth import resolve_codex_runtime_credentials

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state("global-access", "global-refresh"),
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state("profile-local-access", "profile-local-refresh"),
    }))

    creds = resolve_codex_runtime_credentials(refresh_if_expiring=False)

    assert creds["api_key"] == "global-access"
    assert creds["source"] == "hermes-global-auth-store"


def test_codex_runtime_refreshes_and_writes_global_store_for_profile_fallback(profile_env, monkeypatch):
    import hermes_cli.auth as auth

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state("global-access", "global-refresh"),
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={}))

    def fake_refresh(access_token, refresh_token, *, timeout_seconds=20.0):
        assert access_token == "global-access"
        assert refresh_token == "global-refresh"
        return {
            "access_token": "new-global-access",
            "refresh_token": "new-global-refresh",
            "last_refresh": "2026-01-02T00:00:00Z",
        }

    monkeypatch.setattr(auth, "refresh_codex_oauth_pure", fake_refresh)

    creds = auth.resolve_codex_runtime_credentials(force_refresh=True)

    assert creds["api_key"] == "new-global-access"
    global_data = json.loads((profile_env["global"] / "auth.json").read_text())
    assert global_data["providers"]["openai-codex"]["tokens"] == {
        "access_token": "new-global-access",
        "refresh_token": "new-global-refresh",
    }
    profile_data = json.loads((profile_env["profile"] / "auth.json").read_text())
    assert "openai-codex" not in profile_data.get("providers", {})


def test_codex_concurrent_profile_workers_share_one_global_refresh(profile_env, monkeypatch):
    import hermes_cli.auth as auth

    expired_access = _jwt_with_exp(int(time.time()) - 3600)
    fresh_access = _jwt_with_exp(int(time.time()) + 86400)
    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state(expired_access, "global-refresh"),
    }))
    _write(profile_env["profile"] / "auth.json", _make_auth_store(providers={}))

    refresh_started = threading.Event()
    call_lock = threading.Lock()
    refresh_calls: list[tuple[str, str]] = []

    def fake_refresh(access_token, refresh_token, *, timeout_seconds=20.0):
        with call_lock:
            refresh_calls.append((access_token, refresh_token))
        refresh_started.set()
        # Keep the selected global auth-file lock held long enough for the
        # second worker to contend on it, then re-read the refreshed store.
        time.sleep(0.2)
        return {
            "access_token": fresh_access,
            "refresh_token": "new-global-refresh",
            "last_refresh": "2026-01-02T00:00:00Z",
        }

    monkeypatch.setattr(auth, "refresh_codex_oauth_pure", fake_refresh)

    def resolve() -> dict:
        return auth.resolve_codex_runtime_credentials(
            refresh_if_expiring=True,
            refresh_skew_seconds=60,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(resolve)
        assert refresh_started.wait(timeout=2.0)
        second = pool.submit(resolve)
        results = [first.result(timeout=5.0), second.result(timeout=5.0)]

    assert refresh_calls == [(expired_access, "global-refresh")]
    assert [result["api_key"] for result in results] == [fresh_access, fresh_access]
    assert {result["source"] for result in results} == {"hermes-global-auth-store"}
    assert {result["auth_store"] for result in results} == {str(profile_env["global"] / "auth.json")}

    global_data = json.loads((profile_env["global"] / "auth.json").read_text())
    assert global_data["providers"]["openai-codex"]["tokens"] == {
        "access_token": fresh_access,
        "refresh_token": "new-global-refresh",
    }
    profile_data = json.loads((profile_env["profile"] / "auth.json").read_text())
    assert "openai-codex" not in profile_data.get("providers", {})


def test_codex_classic_mode_uses_local_store(tmp_path, monkeypatch):
    import hermes_constants
    from hermes_cli.auth import resolve_codex_runtime_credentials

    global_root = tmp_path / "classic-hermes"
    global_root.mkdir()
    monkeypatch.setattr(hermes_constants, "get_default_hermes_root", lambda: global_root)
    monkeypatch.setenv("HERMES_HOME", str(global_root))
    _write(global_root / "auth.json", _make_auth_store(providers={
        "openai-codex": _codex_state("classic-access", "classic-refresh"),
    }))

    creds = resolve_codex_runtime_credentials(refresh_if_expiring=False)

    assert creds["api_key"] == "classic-access"
    assert creds["source"] == "hermes-auth-store"
    assert creds["auth_store"] == str(global_root / "auth.json")


def test_save_codex_tokens_clears_stale_last_auth_error(profile_env):
    import hermes_cli.auth as auth

    _write(profile_env["global"] / "auth.json", _make_auth_store(providers={
        "openai-codex": {
            **_codex_state("old-access", "old-refresh"),
            "last_auth_error": {"code": "refresh_token_reused"},
        },
    }))

    auth._save_codex_tokens(
        {"access_token": "new-access", "refresh_token": "new-refresh"},
        auth_file=profile_env["global"] / "auth.json",
    )

    global_data = json.loads((profile_env["global"] / "auth.json").read_text())
    state = global_data["providers"]["openai-codex"]
    assert state["tokens"] == {"access_token": "new-access", "refresh_token": "new-refresh"}
    assert "last_auth_error" not in state

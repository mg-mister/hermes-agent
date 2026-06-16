import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


async def _return_background_result(_fn):
    return {
        "final_response": "done\nMEDIA:/etc/passwd\nMEDIA:{valid_path}",
    }


def _make_runner(adapter, result_text):
    from gateway.config import Platform
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._thread_metadata_for_source = MagicMock(return_value={"thread_id": "topic"})
    runner._resolve_session_agent_runtime = MagicMock(return_value=("test-model", {"api_key": "test-key"}))
    runner._resolve_session_reasoning_config = MagicMock(return_value={})
    runner._resolve_turn_agent_config = MagicMock(
        return_value={
            "model": "test-model",
            "runtime": {"api_key": "test-key"},
            "request_overrides": None,
        }
    )
    runner._provider_routing = {}
    runner._load_service_tier = MagicMock(return_value=None)
    runner._service_tier = None
    runner._reasoning_config = {}
    runner._cleanup_agent_resources = MagicMock()

    async def _executor(_fn):
        return {"final_response": result_text}

    runner._run_in_executor_with_context = _executor
    return runner


def _make_source():
    from gateway.config import Platform

    return SimpleNamespace(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="user-1",
        chat_name="Chat",
        chat_type="private",
        thread_id=None,
    )


def test_background_task_filters_invalid_media_paths_before_platform_send(tmp_path, monkeypatch):
    """The /background completion path must reuse the shared MEDIA path guard.

    Regression: _run_background_task extracted MEDIA tags and sent every path
    directly via send_document, bypassing BasePlatformAdapter path validation.
    """
    valid = tmp_path / "safe-report.txt"
    valid.write_text("ok")
    monkeypatch.setenv("HERMES_MEDIA_ALLOW_DIRS", str(tmp_path))
    monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "1")
    monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

    response = f"done\nMEDIA:/etc/passwd\nMEDIA:{valid}"
    adapter = MagicMock()
    adapter.extract_media.return_value = ([('/etc/passwd', False), (str(valid), False)], "done")
    adapter.extract_images.return_value = ([], "done")
    adapter.send = AsyncMock()
    adapter.send_document = AsyncMock()
    adapter.send_voice = AsyncMock()
    adapter.send_video = AsyncMock()
    adapter.send_image = AsyncMock()
    adapter.send_image_file = AsyncMock()

    runner = _make_runner(adapter, response)
    source = _make_source()

    asyncio.run(runner._run_background_task("make report", source, "task-1"))

    adapter.send_document.assert_awaited_once()
    sent_path = adapter.send_document.await_args.kwargs["file_path"]
    assert sent_path == str(valid.resolve())
    assert sent_path != "/etc/passwd"

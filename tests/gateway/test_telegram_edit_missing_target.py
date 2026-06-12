import logging

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.telegram import TelegramAdapter


class _MissingEditTargetBot:
    async def edit_message_text(self, **kwargs):
        raise Exception("Message to edit not found")


@pytest.mark.asyncio
async def test_missing_edit_target_nonfinalize_falls_back_without_warning(caplog):
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = _MissingEditTargetBot()

    with caplog.at_level(logging.WARNING, logger="gateway.platforms.telegram"):
        result = await adapter.edit_message("123", "456", "hello", finalize=False)

    assert result.success is False
    assert result.error == "Message to edit not found"
    assert not caplog.records


@pytest.mark.asyncio
async def test_missing_edit_target_finalize_does_not_retry_plain_text_or_warn(caplog):
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = _MissingEditTargetBot()

    with caplog.at_level(logging.WARNING, logger="gateway.platforms.telegram"):
        result = await adapter.edit_message("123", "456", "**hello**", finalize=True)

    assert result.success is False
    assert result.error == "Message to edit not found"
    assert not caplog.records

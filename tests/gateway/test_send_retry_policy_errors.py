"""Regression tests for terminal policy errors in gateway send retry handling."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult


class PolicyErrorAdapter(BasePlatformAdapter):
    def __init__(self, error: str):
        super().__init__(PlatformConfig(enabled=True), Platform.TELEGRAM)
        self.error = error
        self.calls = 0

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Any = None,
    ) -> SendResult:
        self.calls += 1
        return SendResult(success=False, error=self.error, retryable=False)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {}


@pytest.mark.asyncio
async def test_terminal_policy_error_does_not_plain_text_fallback(caplog):
    adapter = PolicyErrorAdapter("comment_body_too_long")

    result = await adapter._send_with_retry("issue", "long markdown")

    assert result.success is False
    assert result.error == "comment_body_too_long"
    assert adapter.calls == 1
    assert "Fallback send also failed" not in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        "comment_not_human_facing",
        "comment_not_human_useful",
        "comment_failed_redaction",
        "non_canary_issue",
    ],
)
def test_terminal_policy_error_classifier(error):
    assert BasePlatformAdapter._is_terminal_policy_error(error) is True

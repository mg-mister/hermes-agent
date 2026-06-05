"""Tests for delegate_tool toolset scoping.

Verifies that subagents cannot gain tools that the parent does not have.
The LLM controls the `toolsets` parameter — without intersection with the
parent's enabled_toolsets, it can escalate privileges by requesting
arbitrary toolsets.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tools.delegate_tool import (
    _SUBAGENT_TOOLSETS,
    _build_child_agent,
    _strip_blocked_tools,
)


class TestToolsetIntersection:
    """Subagent toolsets must be a subset of parent's enabled_toolsets."""

    def test_requested_toolsets_intersected_with_parent(self):
        """LLM requests toolsets parent doesn't have — extras are dropped."""
        parent = SimpleNamespace(enabled_toolsets=["terminal", "file"])

        # Simulate the intersection logic from _build_child_agent
        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["terminal", "file", "web", "browser", "rl"]
        scoped = [t for t in requested if t in parent_toolsets]

        assert sorted(scoped) == ["file", "terminal"]
        assert "web" not in scoped
        assert "browser" not in scoped
        assert "rl" not in scoped

    def test_all_requested_toolsets_available_on_parent(self):
        """LLM requests subset of parent tools — all pass through."""
        parent = SimpleNamespace(enabled_toolsets=["terminal", "file", "web", "browser"])

        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["terminal", "web"]
        scoped = [t for t in requested if t in parent_toolsets]

        assert sorted(scoped) == ["terminal", "web"]

    def test_no_toolsets_requested_inherits_parent(self):
        """When toolsets is None/empty, child inherits parent's set."""
        parent_toolsets = ["terminal", "file", "web"]
        child = _strip_blocked_tools(parent_toolsets)
        assert "terminal" in child
        assert "file" in child
        assert "web" in child

    def test_strip_blocked_removes_delegation(self):
        """Blocked toolsets (delegation, clarify, etc.) are always removed."""
        child = _strip_blocked_tools(["terminal", "delegation", "clarify", "memory"])
        assert "delegation" not in child
        assert "clarify" not in child
        assert "memory" not in child
        assert "terminal" in child

    def test_strip_blocked_removes_kanban_from_delegate_children(self):
        """Delegate children must not be able to request Kanban lifecycle tools."""
        child = _strip_blocked_tools(["terminal", "file", "kanban"])
        assert child == ["terminal", "file"]
        assert "kanban" not in child

    def test_subagent_toolset_hint_does_not_advertise_kanban(self):
        """The model-facing delegate_task schema must not list kanban as requestable."""
        assert "kanban" not in _SUBAGENT_TOOLSETS

    def test_empty_intersection_yields_empty_toolsets(self):
        """If parent has no overlap with requested, child gets nothing extra."""
        parent = SimpleNamespace(enabled_toolsets=["terminal"])

        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["web", "browser"]
        scoped = [t for t in requested if t in parent_toolsets]

        assert scoped == []

    def test_delegate_child_in_kanban_worker_passes_kanban_disabled_toolset(
        self, monkeypatch
    ):
        """HERMES_KANBAN_TASK auto-inclusion must not re-add kanban to child agents.

        Regression for incident t_65695d63 / source t_6ba07875 / remediation
        t_cb03fc09: a delegated read-only review inherited Kanban tools and
        completed/commented its parent task.
        """
        monkeypatch.setenv("HERMES_KANBAN_TASK", "t_parent")
        parent = MagicMock()
        parent.base_url = "https://example.invalid/api"
        parent.api_key = "test-key"
        parent.provider = "openrouter"
        parent.api_mode = "chat_completions"
        parent.model = "test/model"
        parent.platform = "cli"
        parent.enabled_toolsets = ["terminal", "file", "kanban"]
        parent.providers_allowed = None
        parent.providers_ignored = None
        parent.providers_order = None
        parent.provider_sort = None
        parent.openrouter_min_coding_score = None
        parent._session_db = None
        parent._delegate_depth = 0
        parent._active_children = []
        parent._print_fn = None
        parent.tool_progress_callback = None

        mock_child = MagicMock()
        with patch("run_agent.AIAgent", return_value=mock_child) as mock_agent:
            _build_child_agent(
                task_index=0,
                goal="child",
                context="ctx",
                parent_agent=parent,
                max_iterations=1,
                model=None,
                task_count=1,
                toolsets=["terminal", "file", "kanban"],
            )

        kwargs = mock_agent.call_args.kwargs
        assert kwargs["enabled_toolsets"] == ["terminal", "file"]
        assert "kanban" in kwargs["disabled_toolsets"]

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import main
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

# Events shaped like the Strands stream: some are passed through, some filtered.
TOOL_USE_START_EVENT = {"event": {"contentBlockStart": {"start": {"toolUse": {"name": "check_aws_health"}}}}}
EMPTY_START_EVENT = {"event": {"contentBlockStart": {"start": {}}}}
TEXT_DELTA_EVENT = {"event": {"contentBlockDelta": {"delta": {"text": "hi"}}}}


@pytest.fixture(autouse=True)
def clear_agent_cache():
    """Keep lru_cached agents from leaking between tests."""
    main._get_agent.cache_clear()
    yield
    main._get_agent.cache_clear()


def collect(async_gen):
    """Drain an async generator from sync test code."""
    async def _run():
        return [event async for event in async_gen]
    return asyncio.run(_run())


def make_agent(events):
    """A mock agent whose stream_async yields the given events."""
    async def stream_async(prompt):
        for event in events:
            yield event
    agent = MagicMock()
    agent.stream_async = stream_async
    return agent


class TestGetAgent:
    def test_builds_agent_with_wiring(self):
        with patch.object(main, "load_model") as load_model, \
             patch.object(main, "get_memory_session_manager") as get_mgr, \
             patch.object(main, "Agent") as agent_cls:
            result = main._get_agent("s1", "alice")

        assert result is agent_cls.return_value
        kwargs = agent_cls.call_args.kwargs
        assert kwargs["model"] is load_model.return_value
        assert kwargs["session_manager"] is get_mgr.return_value
        assert isinstance(kwargs["conversation_manager"], NullConversationManager)
        assert kwargs["system_prompt"] == main.DEFAULT_SYSTEM_PROMPT
        assert main.check_aws_health in kwargs["tools"]
        get_mgr.assert_called_once_with("s1", "alice")

    def test_same_session_and_actor_reuses_agent(self):
        with patch.object(main, "load_model"), \
             patch.object(main, "get_memory_session_manager"), \
             patch.object(main, "Agent") as agent_cls:
            first = main._get_agent("s1", "alice")
            second = main._get_agent("s1", "alice")
            third = main._get_agent("s2", "alice")

        assert first is second
        assert agent_cls.call_count == 2  # s1 cached, s2 built fresh
        assert third is not None


class TestInvokeEntrypoint:
    def invoke(self, payload, context, events):
        handler = main.app.handlers["main"]
        with patch.object(main, "_get_agent", return_value=make_agent(events)) as get_agent:
            results = collect(handler(payload, context))
        return results, get_agent

    def test_streams_agent_events(self):
        context = SimpleNamespace(session_id="sess-1")
        results, get_agent = self.invoke(
            {"prompt": "Any incidents?", "actorId": "alice"}, context, [TEXT_DELTA_EVENT]
        )
        assert results == [TEXT_DELTA_EVENT]
        get_agent.assert_called_once_with("sess-1", "alice")

    def test_missing_session_id_falls_back_to_default(self):
        results, get_agent = self.invoke({"prompt": "hi"}, SimpleNamespace(), [])
        assert results == []
        get_agent.assert_called_once_with("default-session", "default")

    def test_filters_non_dict_and_eventless_items(self):
        events = ["not a dict", {"no_event_key": 1}, TEXT_DELTA_EVENT]
        results, _ = self.invoke({"prompt": "hi"}, SimpleNamespace(), events)
        assert results == [TEXT_DELTA_EVENT]

    def test_filters_empty_content_block_start_but_keeps_tool_use_start(self):
        events = [EMPTY_START_EVENT, TOOL_USE_START_EVENT, TEXT_DELTA_EVENT]
        results, _ = self.invoke({"prompt": "hi"}, SimpleNamespace(), events)
        assert results == [TOOL_USE_START_EVENT, TEXT_DELTA_EVENT]

    def test_invalid_payload_raises(self):
        handler = main.app.handlers["main"]
        with pytest.raises(ValueError, match="prompt must be a string"):
            collect(handler({"prompt": 42}, SimpleNamespace()))

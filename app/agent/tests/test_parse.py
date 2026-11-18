import pytest

from parse import _strip_trailing_tool_use, parse_payload


def user_msg(text):
    return {"role": "user", "content": [{"text": text}]}


def tool_use_msg(extra_blocks=None):
    content = [{"toolUse": {"name": "check_aws_health", "toolUseId": "t1", "input": {}}}]
    if extra_blocks:
        content = extra_blocks + content
    return {"role": "assistant", "content": content}


class TestStripTrailingToolUse:
    def test_clean_history_is_unchanged(self):
        messages = [user_msg("hi"), {"role": "assistant", "content": [{"text": "hello"}]}]
        assert _strip_trailing_tool_use(messages) == messages

    def test_empty_list_is_unchanged(self):
        assert _strip_trailing_tool_use([]) == []

    def test_trailing_tool_use_only_message_is_dropped(self):
        messages = [user_msg("hi"), tool_use_msg()]
        assert _strip_trailing_tool_use(messages) == [user_msg("hi")]

    def test_mixed_content_keeps_non_tool_blocks(self):
        messages = [user_msg("hi"), tool_use_msg(extra_blocks=[{"text": "checking..."}])]
        result = _strip_trailing_tool_use(messages)
        assert result == [
            user_msg("hi"),
            {"role": "assistant", "content": [{"text": "checking..."}]},
        ]

    def test_multiple_trailing_tool_use_messages_are_all_dropped(self):
        messages = [user_msg("hi"), tool_use_msg(), tool_use_msg()]
        assert _strip_trailing_tool_use(messages) == [user_msg("hi")]

    def test_all_messages_dropped_when_every_message_is_tool_use(self):
        assert _strip_trailing_tool_use([tool_use_msg()]) == []

    def test_stops_at_first_clean_message_without_touching_earlier_tool_use(self):
        earlier = tool_use_msg()
        messages = [earlier, user_msg("follow-up")]
        assert _strip_trailing_tool_use(messages) == [earlier, user_msg("follow-up")]

    def test_input_list_is_not_mutated(self):
        messages = [user_msg("hi"), tool_use_msg()]
        _strip_trailing_tool_use(messages)
        assert len(messages) == 2

    def test_rejects_non_list(self):
        with pytest.raises(ValueError, match="must be a list"):
            _strip_trailing_tool_use("not a list")

    def test_rejects_non_dict_message(self):
        with pytest.raises(ValueError, match="must be an object"):
            _strip_trailing_tool_use(["not a dict"])

    def test_rejects_non_list_content(self):
        with pytest.raises(ValueError, match="list of content blocks"):
            _strip_trailing_tool_use([{"role": "user", "content": "plain string"}])

    def test_rejects_non_dict_content_block(self):
        with pytest.raises(ValueError, match="list of content blocks"):
            _strip_trailing_tool_use([{"role": "user", "content": ["plain string"]}])


class TestParsePayload:
    def test_plain_prompt(self):
        assert parse_payload({"prompt": "Any incidents?"}) == ("Any incidents?", "default")

    def test_missing_prompt_defaults_to_empty_string(self):
        assert parse_payload({}) == ("", "default")

    def test_actor_id_is_passed_through(self):
        assert parse_payload({"prompt": "hi", "actorId": "alice"}) == ("hi", "alice")

    def test_empty_actor_id_falls_back_to_default(self):
        assert parse_payload({"prompt": "hi", "actorId": ""}) == ("hi", "default")

    def test_messages_take_precedence_over_prompt(self):
        messages = [user_msg("hi")]
        result, actor_id = parse_payload({"messages": messages, "prompt": "ignored"})
        assert result == messages
        assert actor_id == "default"

    def test_messages_are_stripped_of_trailing_tool_use(self):
        result, _ = parse_payload({"messages": [user_msg("hi"), tool_use_msg()]})
        assert result == [user_msg("hi")]

    def test_rejects_non_dict_payload(self):
        with pytest.raises(ValueError, match="JSON object"):
            parse_payload(["not", "a", "dict"])

    def test_rejects_non_string_actor_id(self):
        with pytest.raises(ValueError, match="actorId"):
            parse_payload({"prompt": "hi", "actorId": 42})

    def test_rejects_non_string_prompt(self):
        with pytest.raises(ValueError, match="prompt"):
            parse_payload({"prompt": 42})

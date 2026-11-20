from unittest.mock import patch

from model.load import load_model


def test_load_model_builds_bedrock_model_with_pinned_id():
    with patch("model.load.BedrockModel") as bedrock_model:
        result = load_model()

    bedrock_model.assert_called_once_with(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    assert result is bedrock_model.return_value

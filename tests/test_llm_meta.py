"""Tests for the T1 LLM client extension (Meta configuration).

All offline: ``requests.post`` is mocked. Existing behaviour is covered by
tests/test_llm.py (unchanged); these tests cover the new T1 surface:
detailed result (model_returned/usage/finish_reason), exactly one retry on
network errors, no retry on HTTP errors, configurable system role, and the
opt-in JSON mode. Fixtures here are SYNTHETIC provider envelopes.
"""
from __future__ import annotations

from unittest import mock

import requests

from services.common.llm import (
    LLMConfig,
    chat_completion,
    chat_completion_detailed,
)


def _config(**overrides) -> LLMConfig:
    cfg = LLMConfig()
    cfg.base_url = "https://api.meta.ai/v1"
    cfg.api_key = "k"
    cfg.model = "muse-spark-1.3"
    cfg.timeout_s = 5.0
    cfg.system_role = "system"
    cfg.json_mode = False
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def _ok_envelope(content="FEN_META_OK"):
    resp = mock.Mock()
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json.return_value = {
        "model": "muse-spark-1.3",
        "choices": [
            {"message": {"content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
    }
    return resp


def test_detailed_returns_model_usage_finish_reason():
    with mock.patch("services.common.llm.requests.post", return_value=_ok_envelope()) as post:
        result = chat_completion_detailed(_config(), "sys", "usr")
    assert result is not None
    assert result.text == "FEN_META_OK"
    assert result.model_returned == "muse-spark-1.3"
    assert result.usage == {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}
    assert result.finish_reason == "stop"
    _, kwargs = post.call_args
    assert kwargs["json"]["messages"][0] == {"role": "system", "content": "sys"}
    assert "response_format" not in kwargs["json"]  # JSON mode off by default


def test_detailed_never_returns_credentials():
    with mock.patch("services.common.llm.requests.post", return_value=_ok_envelope()):
        result = chat_completion_detailed(_config(), "sys", "usr")
    assert "k" != result.text
    assert not hasattr(result, "api_key")
    assert not hasattr(result, "headers")


def test_system_role_is_configurable():
    with mock.patch("services.common.llm.requests.post", return_value=_ok_envelope()) as post:
        chat_completion_detailed(_config(system_role="developer"), "sys", "usr")
    _, kwargs = post.call_args
    assert kwargs["json"]["messages"][0]["role"] == "developer"


def test_json_mode_opt_in_sends_response_format():
    with mock.patch("services.common.llm.requests.post", return_value=_ok_envelope()) as post:
        chat_completion_detailed(_config(), "sys", "usr", json_mode=True)
    _, kwargs = post.call_args
    assert kwargs["json"]["response_format"] == {"type": "json_object"}


def test_json_mode_from_config():
    with mock.patch("services.common.llm.requests.post", return_value=_ok_envelope()) as post:
        chat_completion_detailed(_config(json_mode=True), "sys", "usr")
    _, kwargs = post.call_args
    assert kwargs["json"]["response_format"] == {"type": "json_object"}


def test_exactly_one_retry_on_connection_error_then_success():
    with mock.patch(
        "services.common.llm.requests.post",
        side_effect=[requests.ConnectionError("down"), _ok_envelope()],
    ) as post:
        result = chat_completion_detailed(_config(), "sys", "usr")
    assert result is not None and result.text == "FEN_META_OK"
    assert post.call_count == 2


def test_retry_exhausted_returns_none_after_two_attempts():
    with mock.patch(
        "services.common.llm.requests.post",
        side_effect=requests.Timeout("slow"),
    ) as post:
        assert chat_completion_detailed(_config(), "sys", "usr") is None
    assert post.call_count == 2  # initial + exactly one retry, never more


def test_no_retry_on_http_error():
    resp = mock.Mock()
    resp.raise_for_status = mock.Mock(
        side_effect=requests.HTTPError("401", response=mock.Mock(status_code=401))
    )
    with mock.patch("services.common.llm.requests.post", return_value=resp) as post:
        assert chat_completion_detailed(_config(), "sys", "usr") is None
    assert post.call_count == 1


def test_no_retry_on_malformed_envelope():
    resp = _ok_envelope()
    resp.json.side_effect = ValueError("bad json")
    with mock.patch("services.common.llm.requests.post", return_value=resp) as post:
        assert chat_completion_detailed(_config(), "sys", "usr") is None
    assert post.call_count == 1


def test_text_wrapper_still_works_and_shares_retry():
    with mock.patch(
        "services.common.llm.requests.post",
        side_effect=[requests.ConnectionError("down"), _ok_envelope("validated")],
    ) as post:
        assert chat_completion(_config(), "sys", "usr") == "validated"
    assert post.call_count == 2

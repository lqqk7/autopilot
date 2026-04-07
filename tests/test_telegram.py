import pytest
from unittest.mock import patch, MagicMock
from autopilot.notifications.telegram import TelegramNotifier


def test_send_pause_notification():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        notifier = TelegramNotifier(token="fake-token", chat_id="12345")
        notifier.send_pause(phase="DEV_LOOP", reason="Max retries exceeded")
        assert mock_post.called
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json", {})
        assert "HUMAN_PAUSE" in body.get("text", "")


def test_send_feature_done():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        notifier = TelegramNotifier(token="fake-token", chat_id="12345")
        notifier.send_feature_done(title="用户登录", elapsed=42.5, progress=(1, 5))
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json", {})
        assert "1/5" in body.get("text", "")


def test_send_done():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        notifier = TelegramNotifier(token="fake-token", chat_id="12345")
        notifier.send_done(total_seconds=3600.0, knowledge_count=3)
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json", {})
        assert "DONE" in body.get("text", "")

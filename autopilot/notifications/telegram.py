from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id
        self._base = f"https://api.telegram.org/bot{token}"

    def _send(self, text: str) -> None:
        try:
            resp = httpx.post(
                f"{self._base}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Telegram send failed: %s", e)

    def send_pause(self, phase: str, reason: str) -> None:
        self._send(f"⏸ *HUMAN_PAUSE*\n\nPhase: `{phase}`\nReason: {reason}")

    def send_feature_done(self, title: str, elapsed: float, progress: tuple[int, int]) -> None:
        done, total = progress
        self._send(f"✅ *Feature Done* ({done}/{total})\n\n`{title}` — {elapsed:.0f}s")

    def send_done(self, total_seconds: float, knowledge_count: int) -> None:
        mins = total_seconds / 60
        self._send(f"🎉 *DONE*\n\nTotal time: {mins:.0f}m\nKnowledge entries: {knowledge_count}")

    def send_timeout(self, phase: str, retries: int) -> None:
        self._send(f"⚠️ *Timeout*\n\nPhase: `{phase}` — retry {retries}")

    def send_backend_switch(self, from_backend: str, to_backend: str, reason: str) -> None:
        self._send(f"🔄 *Backend Switch*\n\n`{from_backend}` → `{to_backend}`\nReason: {reason}")

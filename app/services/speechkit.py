from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class SpeechKitService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def transcribe_ogg(self, file_path: str | Path) -> str:
        if not self.settings.yandex_speechkit_api_key or not self.settings.yandex_speechkit_folder_id:
            return (
                "Распознавание голоса не настроено. "
                "Добавьте YANDEX_SPEECHKIT_API_KEY и YANDEX_SPEECHKIT_FOLDER_ID в .env."
            )

        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError("Voice file is empty or missing")

        url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"

        params = {
            "folderId": self.settings.yandex_speechkit_folder_id,
            "lang": self.settings.yandex_stt_language,
            "format": "oggopus",
            "sampleRateHertz": "48000",
        }

        headers = {
            "Authorization": f"Api-Key {self.settings.yandex_speechkit_api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    url,
                    params=params,
                    headers=headers,
                    content=path.read_bytes(),
                )
                response.raise_for_status()
                data = response.json()

            if "result" not in data:
                raise RuntimeError(f"SpeechKit response has no result: {data}")

            return str(data["result"]).strip()
        except Exception:
            logger.exception("SpeechKit STT failed")
            raise

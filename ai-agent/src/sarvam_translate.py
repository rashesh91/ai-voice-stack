import logging
import httpx

SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"
logger = logging.getLogger(__name__)


class SarvamTranslate:
    def __init__(self, *, api_key: str):
        self._api_key = api_key

    async def to_lang(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text to target_lang. Returns original if translation not needed or fails."""
        if not text.strip():
            return text
        # API rejects same-language pairs
        if source_lang == target_lang:
            return text
        # Don't translate to English — LLM handles it natively
        if target_lang == "en-IN":
            return text

        payload = {
            "input": text,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "speaker_gender": "Female",
            "mode": "formal",
            "model": "mayura:v1",
            "enable_preprocessing": True,
        }
        headers = {
            "api-subscription-key": self._api_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(SARVAM_TRANSLATE_URL, json=payload, headers=headers)
            resp.raise_for_status()
            translated = resp.json()["translated_text"]
            logger.info("translate %s→%s: %r → %r", source_lang, target_lang,
                        text[:50], translated[:50])
            return translated
        except Exception:
            logger.exception("translate failed %s→%s, using original", source_lang, target_lang)
            return text

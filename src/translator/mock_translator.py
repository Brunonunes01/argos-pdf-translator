from __future__ import annotations

from .base import Translator


class MockTranslator(Translator):
    def translate(self, text: str, source_lang: str = "en", target_lang: str = "pt-BR") -> str:
        return "[TRADUCAO MOCK] " + text

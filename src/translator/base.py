from __future__ import annotations

from abc import ABC, abstractmethod


class Translator(ABC):
    @abstractmethod
    def translate(self, text: str, source_lang: str = "en", target_lang: str = "pt-BR") -> str:
        raise NotImplementedError

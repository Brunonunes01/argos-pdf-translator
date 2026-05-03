from __future__ import annotations

import os
import time

from .base import Translator


TRANSLATION_INSTRUCTIONS = (
    "Traduza o texto abaixo do ingles para portugues do Brasil. "
    "Mantenha o sentido tecnico, nao resuma, nao adicione explicacoes, "
    "preserve numeros, formulas, unidades, nomes proprios e siglas. "
    "Retorne somente a traducao."
)


class GeminiTranslator(Translator):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY nao configurada. Use traducao Mock ou configure o arquivo .env.")

        from google import genai
        from google.genai import types

        self.client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 60000},
        )
        self.types = types
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
        self.max_retries = 3
        self.base_delay = 2

    def translate(self, text: str, source_lang: str = "en", target_lang: str = "pt-BR") -> str:
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=text,
                    config=self.types.GenerateContentConfig(
                        system_instruction=TRANSLATION_INSTRUCTIONS,
                        temperature=0.2,
                    ),
                )
                translated = (response.text or "").strip()
                if not translated:
                    raise RuntimeError("A resposta do Gemini veio vazia.")
                return translated
                
            except Exception as exc:
                last_exception = exc
                message = str(exc)
                is_rate_limit = "RESOURCE_EXHAUSTED" in message or "429" in message or "rate limit" in message.casefold()
                
                if is_rate_limit:
                    raise RuntimeError(
                        "Quota do Gemini esgotada ou indisponivel para este modelo. "
                        "Tente novamente mais tarde ou altere GEMINI_MODEL no .env."
                    ) from exc
                
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                
                raise
        
        raise RuntimeError(f"Gemini falhou apos {self.max_retries} tentativas: {last_exception}")

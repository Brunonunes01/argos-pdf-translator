from __future__ import annotations

import os
import time

from openai import OpenAI, RateLimitError, APIError

from .base import Translator


TRANSLATION_INSTRUCTIONS = (
    "Traduza o texto abaixo do ingles para portugues do Brasil. "
    "Mantenha o sentido tecnico, nao resuma, nao adicione explicacoes, "
    "preserve numeros, formulas, unidades, nomes proprios e siglas. "
    "Retorne somente a traducao."
)


class OpenAITranslator(Translator):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY nao configurada. Use traducao Mock ou configure o arquivo .env.")
        self.client = OpenAI(
            api_key=api_key,
            timeout=60.0,
        )
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.max_retries = 3
        self.base_delay = 2

    def translate(self, text: str, source_lang: str = "en", target_lang: str = "pt-BR") -> str:
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": TRANSLATION_INSTRUCTIONS},
                        {"role": "user", "content": text},
                    ],
                )
                return response.output_text.strip()
                
            except RateLimitError as exc:
                raise RuntimeError(
                    "Quota da OpenAI esgotada. Tente novamente mais tarde ou altere OPENAI_MODEL no .env."
                ) from exc
                
            except APIError as exc:
                last_exception = exc
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise
        
        raise RuntimeError(f"OpenAI falhou apos {self.max_retries} tentativas: {last_exception}")

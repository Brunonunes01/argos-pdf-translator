from __future__ import annotations

import os

from .base import Translator


LANGUAGE_ALIASES = {
    "pt-BR": "pt",
    "pt_BR": "pt",
    "en-US": "en",
    "en_US": "en",
}


class ArgosTranslator(Translator):
    def __init__(self, auto_install: bool | None = None) -> None:
        try:
            import argostranslate.package
            import argostranslate.translate
        except ImportError as exc:
            raise RuntimeError(
                "Argos Translate nao esta instalado. Rode: pip install argostranslate"
            ) from exc

        self.package = argostranslate.package
        self.translate_module = argostranslate.translate
        self.auto_install = (
            auto_install
            if auto_install is not None
            else os.getenv("ARGOS_AUTO_INSTALL", "1") != "0"
        )

    def translate(self, text: str, source_lang: str = "en", target_lang: str = "pt-BR") -> str:
        from_code = self._normalize_language(source_lang)
        to_code = self._normalize_language(target_lang)
        self._ensure_language_pair(from_code, to_code)

        translated = self.translate_module.translate(text, from_code, to_code).strip()
        if not translated:
            raise RuntimeError("A resposta do Argos veio vazia.")
        return translated

    def _ensure_language_pair(self, from_code: str, to_code: str) -> None:
        if self._has_language_pair(from_code, to_code):
            return

        if not self.auto_install:
            raise RuntimeError(
                f"Pacote Argos {from_code}->{to_code} nao instalado. "
                "Ative ARGOS_AUTO_INSTALL=1 ou instale o pacote pelo argospm."
            )

        self.package.update_package_index()
        available_packages = self.package.get_available_packages()
        package_to_install = next(
            (
                package
                for package in available_packages
                if package.from_code == from_code and package.to_code == to_code
            ),
            None,
        )
        if package_to_install is None:
            raise RuntimeError(f"Nenhum pacote Argos encontrado para {from_code}->{to_code}.")

        self.package.install_from_path(package_to_install.download())

        if not self._has_language_pair(from_code, to_code):
            raise RuntimeError(f"Pacote Argos {from_code}->{to_code} instalado, mas nao ficou disponivel.")

    def _has_language_pair(self, from_code: str, to_code: str) -> bool:
        installed_languages = self.translate_module.get_installed_languages()
        from_language = next(
            (language for language in installed_languages if language.code == from_code),
            None,
        )
        to_language = next(
            (language for language in installed_languages if language.code == to_code),
            None,
        )
        if from_language is None or to_language is None:
            return False
        return from_language.get_translation(to_language) is not None

    def _normalize_language(self, language: str) -> str:
        return LANGUAGE_ALIASES.get(language, language)

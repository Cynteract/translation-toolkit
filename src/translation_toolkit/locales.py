# locales.py
# Generic locale utilities. Callers supply their own supported_locales / aliases
# (e.g. from a filesystem scan, a DB, a config file) — this class doesn't know
# or care where they came from.

DEFAULT_GOOGLE_TRANSLATE_LOCALE_MAP = {
    "zh": "zh-CN",
    "he": "iw",
}

class LocaleRegistry:
    def __init__(self, supported_locales: dict[str, str], locale_aliases: dict[str, str]):
        self.supported_locales = supported_locales
        self.locale_aliases = locale_aliases
        self.locale_expansion = self._build_expansion()
        self.display_name_to_locale = {v.lower(): k for k, v in supported_locales.items()}

    def _build_expansion(self) -> dict[str, list[str]]:
        expansion: dict[str, list[str]] = {}
        for alias, canonical in self.locale_aliases.items():
            expansion.setdefault(canonical, [canonical])
            if alias not in expansion[canonical]:
                expansion[canonical].append(alias)
        return expansion

    def normalize_locale(self, locale: str) -> str:
        result = self.locale_aliases.get(locale, locale)
        return result if result is not None else locale

    def locale_display_name(self, locale: str) -> str:
        if locale in self.supported_locales:
            return self.supported_locales[locale]
        canonical = self.locale_aliases.get(locale)
        if canonical and canonical in self.supported_locales:
            suffix = locale[len(canonical) + 1:]
            return f"{self.supported_locales[canonical]} ({suffix})"
        return locale
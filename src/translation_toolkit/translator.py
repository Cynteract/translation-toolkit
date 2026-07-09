# translator.py
# Generic translation engine — operates on LocalizationDataset objects,
# no filesystem/Unity/pipeline assumptions baked in.

import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from google.oauth2 import service_account
from google.cloud import translate_v2 as google_translate

from .models import LocalizationDataset
from .locales import DEFAULT_GOOGLE_TRANSLATE_LOCALE_MAP

logger = logging.getLogger(__name__)


class Translator:
    def __init__(
        self,
        service_account_path: str | Path,
        google_locale_map: dict[str, str] | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        max_workers: int = 10,
    ):
        self.service_account_path = Path(service_account_path)
        self.google_locale_map = google_locale_map or DEFAULT_GOOGLE_TRANSLATE_LOCALE_MAP
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.client = self._build_client()

    def _build_client(self):
        if not self.service_account_path.is_file():
            raise FileNotFoundError(f"Service account file not found: {self.service_account_path}")
        credentials = service_account.Credentials.from_service_account_file(
            str(self.service_account_path),
            scopes=["https://www.googleapis.com/auth/cloud-translation"],
        )
        return google_translate.Client(credentials=credentials)

    def translate_text(self, text: str, target_locale: str, source_locale: str = "en") -> str:
        if not text.strip() or not target_locale:
            return ""
        google_locale = self.google_locale_map.get(target_locale) or target_locale
        for attempt in range(self.max_retries):
            try:
                result = self.client.translate(text, target_language=google_locale, source_language=source_locale)
                return result["translatedText"]
            except Exception as e:
                logger.warning(f"[Translate] '{text[:40]}' to '{google_locale}', attempt {attempt + 1}: {e}")
                time.sleep(self.retry_delay)
        logger.error(f"[Translate] All attempts failed for '{text[:40]}' to '{google_locale}'")
        return ""

    def _translate_one(self, task: tuple[str, str, str, str]):
        table_name, entry_id, locale, source_text = task
        translated = self.translate_text(source_text, locale)
        return table_name, entry_id, locale, translated

    def auto_translate(
        self,
        dataset: LocalizationDataset,
        target_locales: list[str],
        locale_expansion: dict[str, list[str]] | None = None,
        source_locale: str = "en",
        on_progress: Optional[Callable[[], None]] = None,
    ) -> LocalizationDataset:
        locale_expansion = locale_expansion or {}

        missing = []
        for table_name, table in dataset.tables.items():
            for entry_id, locales in table.entries.items():
                source_text = locales.get(source_locale, "").strip()
                if source_text:
                    for locale in target_locales:
                        if locale != source_locale and not locales.get(locale, "").strip():
                            missing.append((table_name, entry_id, locale, source_text))

        if not missing:
            logger.info("No missing translations found.")
            return dataset

        logger.info(f"Translating {len(missing)} entries with {self.max_workers} workers...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._translate_one, task): task for task in missing}
            for future in as_completed(futures):
                table_name, entry_id, locale, translated = future.result()
                if translated:
                    for key in locale_expansion.get(locale, [locale]):
                        dataset.add_entry(table_name, entry_id, key, translated)
                if on_progress:
                    on_progress()

        return dataset
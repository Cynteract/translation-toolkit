# models.py
# shared datacasses for localization datasets
# Data order: table -> key -> locale -> value

from dataclasses import dataclass, field
from typing import Dict

@dataclass
class LocalizationTable:
    table_name: str
    # locale: str
    description: str = ""
    entries: Dict[str, Dict[str, str]] = field(default_factory = dict)

    def add_entry(self, key, locale, value) -> None:
        self.entries.setdefault(key, {})[locale] = value
    
    def get_value(self, key, locale) -> str:
        return self.entries.get(key, {}).get(locale, "")

    def has_entry(self, key, locale) -> bool:
        return locale in self.entries.get(key, {})

@dataclass
class LocalizationDataset:
    tables: Dict[str, LocalizationTable] = field(default_factory = dict)

    def add_entry(self, table_name, key, locale, value) -> None:
        if table_name not in self.tables:
            self.tables[table_name] = LocalizationTable(table_name = table_name)
        self.tables[table_name].add_entry(key, locale, value)

    def get_value(self, table_name, key, locale) -> str:
        table = self.tables.get(table_name)
        if not table:
            return ""
        return table.get_value(key, locale)
    
    def has_entry(self, table_name, key, locale) -> bool:
        table = self.tables.get(table_name)
        if not table:
            return False
        return table.has_entry(key, locale)
    
    def get_table(self, table_name) -> LocalizationTable | None:
        return self.tables.get(table_name)
    
    def iter_tables(self):
        return self.tables.items()
    
    def iter_entries(self, table_name):
        for table_name, table in self.tables.items():
            for key, locales in table.entries.items():
                yield table_name, key, locales

    def merge_onto(self, other: "LocalizationDataset") -> "LocalizationDataset":
        """Overlay `other`'s non-empty values onto self, in place. `other` wins on
        conflict; self's existing entries are preserved wherever `other` doesn't
        have a value for that (table, entry, locale). Returns self for convenience.
        Used by connectors (e.g. Sheets sync) that need an external source of
        truth to take priority over the current on-disk/cached state."""
        for table_name, table in other.tables.items():
            for entry_id, locales in table.entries.items():
                for locale, value in locales.items():
                    value = value.strip() if isinstance(value, str) else value
                    if not value:
                        continue
                    self.add_entry(table_name, entry_id, locale, value)
        return self

    def to_json(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        return {
            table_name: table.entries
            for table_name, table in self.tables.items()
        }
    
# fixing type issues with json dumping
    @classmethod
    def from_json(cls, data) -> "LocalizationDataset":
        dataset = cls()

        for table_name, entries in data.items():
            for key, locales in entries.items():
                for locale, value in locales.items():
                    dataset.add_entry(table_name, key, locale, value)

        return dataset
    
    def __len__(self) -> int:
        return len(self.tables)
    
    def is_empty(self) -> bool:
        return not self.tables
    
    def clear(self) -> None:
        self.tables.clear()
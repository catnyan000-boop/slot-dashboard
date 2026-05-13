from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

from src.db.models import StoreCatalog, StoreDefinition


class StoreNormalizer:
    def __init__(self, catalog: StoreCatalog):
        self.catalog = catalog
        self._store_map = catalog.by_store_id()
        self._alias_map = self._build_alias_map()

    @classmethod
    def from_yaml(cls, path: Path) -> "StoreNormalizer":
        return cls(StoreCatalog.from_yaml(path))

    @staticmethod
    def normalize_text(value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "")
        text = re.sub(r"\s+", "", text)
        return text.strip()

    def _build_alias_map(self) -> dict[str, StoreDefinition]:
        alias_map: dict[str, StoreDefinition] = {}
        for store in self.catalog.stores:
            candidates = [store.store_id, store.display_name, store.canonical_name, *store.aliases]
            for candidate in candidates:
                alias_map[self.normalize_text(candidate)] = store
        return alias_map

    def list_stores(self) -> list[StoreDefinition]:
        return self.catalog.stores

    def get_by_store_id(self, store_id: str) -> Optional[StoreDefinition]:
        return self._store_map.get(store_id)

    def resolve(self, raw_name: str) -> Optional[StoreDefinition]:
        normalized = self.normalize_text(raw_name)
        if normalized in self._alias_map:
            return self._alias_map[normalized]
        for alias, store in self._alias_map.items():
            if alias in normalized or normalized in alias:
                return store
        return None


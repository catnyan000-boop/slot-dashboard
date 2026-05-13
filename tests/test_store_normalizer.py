from pathlib import Path

from src.normalizers.store_normalizer import StoreNormalizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_stores_yaml_loads() -> None:
    normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    stores = normalizer.list_stores()
    assert len(stores) == 9
    assert stores[0].store_id == "cosmo_obu"


def test_alias_normalization() -> None:
    normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    resolved = normalizer.resolve("ＫＹＯＲＡＫＵ東海店")
    assert resolved is not None
    assert resolved.store_id == "kyoraku_tokai"


from src.normalizers.machine_normalizer import MachineNormalizer


def test_machine_category_classification() -> None:
    assert MachineNormalizer.categorize_machine("Lパチスロ革命機ヴァルヴレイヴ") == "smart_slot_at"
    assert MachineNormalizer.categorize_machine("マイジャグラーV") == "jug_hana"
    assert MachineNormalizer.categorize_machine("新ハナビ") == "normal_a_type"
    assert MachineNormalizer.categorize_machine("沖ドキ！GOLD-30") == "okidoki_30"
    assert MachineNormalizer.categorize_machine("パチスロ甲鉄城のカバネリ") == "medal_at_art"


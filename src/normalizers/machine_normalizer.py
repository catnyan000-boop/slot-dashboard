from __future__ import annotations

import re
import unicodedata


class MachineNormalizer:
    @staticmethod
    def normalize_name(name: str) -> str:
        text = unicodedata.normalize("NFKC", name or "")
        text = text.replace("　", " ")
        text = re.sub(r"\s+", " ", text)
        text = text.replace("〜", "~")
        text = text.replace("～", "~")
        return text.strip()

    @classmethod
    def categorize_machine(cls, name: str, unit_count: int | None = None) -> str:
        normalized = cls.normalize_name(name)

        if unit_count == 1:
            return "variety"
        if re.search(r"ジャグラー|ハナハナ", normalized):
            return "jug_hana"
        if re.search(
            r"ハナビ|バーサス|アレックス|ディスクアップ|クレア|ゲッタマ|ひぐらし|ファミスタ|ボーナストリガー|BT|約束の扉",
            normalized,
        ):
            return "normal_a_type"
        if re.search(r"沖ドキ|チバリヨ|島唄", normalized):
            return "okidoki_30"
        if re.search(r"^(L|LB)\b|^L\S|^LB\S|スマスロ", normalized):
            return "smart_slot_at"
        if re.search(r"パチスロ|SLOT|スロット|回胴|バジリスク|モンキー|番長|カバネリ", normalized):
            return "medal_at_art"
        return "other"


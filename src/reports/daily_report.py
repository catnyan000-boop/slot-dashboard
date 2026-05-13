from __future__ import annotations


def confidence_to_letter(value: float) -> str:
    if value >= 0.8:
        return "A"
    if value >= 0.62:
        return "B"
    if value >= 0.42:
        return "C"
    return "D"


from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


class StoreDefinition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    store_id: str
    display_name: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    slorepo_slug: str = ""
    event_days: list[str] = Field(default_factory=list)
    prefecture: str = ""
    city: str = ""
    memo: str = ""


class StoreCatalog(BaseModel):
    stores: list[StoreDefinition]

    @classmethod
    def from_yaml(cls, path: Path) -> "StoreCatalog":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    def by_store_id(self) -> dict[str, StoreDefinition]:
        return {store.store_id: store for store in self.stores}


class SourcePageRecord(BaseModel):
    source: str
    store_id: str
    url: str
    report_date: Optional[date] = None
    raw_path: str
    fetched_at: str
    status_code: Optional[int] = None
    content_hash: str


class DailyStoreResultRecord(BaseModel):
    source: str
    store_id: str
    report_date: date
    total_diff: Optional[int] = None
    avg_diff: Optional[float] = None
    avg_game: Optional[float] = None
    win_rate: Optional[float] = None
    total_units: Optional[int] = None
    source_url: str
    created_at: str


class MachineResultRecord(BaseModel):
    source: str
    store_id: str
    report_date: date
    machine_name_raw: str
    machine_name_normalized: str
    machine_category: str
    unit_count: int
    total_diff: Optional[float] = None
    avg_diff: Optional[float] = None
    avg_game: Optional[float] = None
    win_rate: Optional[float] = None
    source_url: str
    created_at: str


class UnitResultRecord(BaseModel):
    source: str
    store_id: str
    report_date: date
    unit_number: str
    machine_name_raw: str
    machine_name_normalized: str
    machine_category: str
    diff: Optional[float] = None
    games: Optional[float] = None
    payout_rate: Optional[float] = None
    bb: Optional[int] = None
    rb: Optional[int] = None
    diff_source: Optional[str] = None
    games_source: Optional[str] = None
    payout_rate_source: Optional[str] = None
    detail_url: Optional[str] = None
    detail_fetched_at: Optional[str] = None
    detail_parse_status: Optional[str] = None
    detail_error: Optional[str] = None
    source_url: str
    created_at: str


class StoreScoreRecord(BaseModel):
    run_id: int
    store_id: str
    target_date: date
    score: float
    confidence: float
    sample_size: int
    reason_json: str


class TargetRecommendationRecord(BaseModel):
    run_id: int
    target_date: date
    store_id: str
    rank: int
    recommended_categories: str
    recommended_machines: str
    recommended_number_patterns: str
    avoid_reason: str = ""
    confidence: str
    reason_text: str


class NormalizedResultKey(BaseModel):
    source: str
    store_id: str
    report_date: date


class NormalizedUnitObservation(BaseModel):
    key: NormalizedResultKey
    unit_number: str
    machine_name_normalized: str
    machine_category: str
    diff: Optional[float] = None
    games: Optional[float] = None
    payout_rate: Optional[float] = None


class NormalizedMachineObservation(BaseModel):
    key: NormalizedResultKey
    machine_name_normalized: str
    machine_category: str
    unit_count: int
    avg_diff: Optional[float] = None
    avg_game: Optional[float] = None
    win_rate: Optional[float] = None

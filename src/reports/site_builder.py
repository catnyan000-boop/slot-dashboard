from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from src.reports.tomorrow_report import run_analysis

SITE_CSS = """\
:root {
  --bg: #f5efe6;
  --surface: #fffaf2;
  --surface-strong: #ffffff;
  --ink: #1f1a17;
  --muted: #6e6258;
  --line: #d7c7b4;
  --accent: #0f766e;
  --accent-soft: #d7f3ef;
  --warn: #b45309;
  --warn-soft: #fff1d6;
  --danger: #b42318;
  --danger-soft: #ffe2df;
  --empty: #5b21b6;
  --empty-soft: #efe4ff;
  --shadow: 0 18px 40px rgba(55, 33, 10, 0.08);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 32%),
    linear-gradient(180deg, #f6f1ea 0%, #f2e9de 100%);
}

a {
  color: inherit;
}

.page {
  width: min(1200px, calc(100% - 32px));
  margin: 0 auto;
  padding: 24px 0 48px;
}

.hero {
  background: linear-gradient(145deg, rgba(255, 250, 242, 0.96), rgba(247, 237, 223, 0.92));
  border: 1px solid rgba(215, 199, 180, 0.8);
  border-radius: 28px;
  box-shadow: var(--shadow);
  padding: 28px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 0.86rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

.hero h1 {
  margin: 0;
  font-size: clamp(1.9rem, 4vw, 3.2rem);
  line-height: 1.1;
}

.hero p {
  color: var(--muted);
  margin: 12px 0 0;
  max-width: 70ch;
}

.hero-alert {
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(180, 35, 24, 0.24);
  background: linear-gradient(180deg, rgba(255, 226, 223, 0.92), rgba(255, 239, 236, 0.92));
}

.hero-alert strong {
  display: block;
  font-size: 1rem;
}

.hero-alert p {
  margin-top: 8px;
  color: #7a271a;
}

.meta-grid,
.summary-grid,
.filter-row,
.card-grid,
.list-grid {
  display: grid;
  gap: 16px;
}

.meta-grid,
.summary-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-top: 20px;
}

.stat,
.panel,
.store-card,
.table-wrap {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(215, 199, 180, 0.95);
  border-radius: 22px;
  box-shadow: var(--shadow);
}

.stat,
.panel {
  padding: 18px;
}

.stat-label,
.panel h2,
.table-wrap h2 {
  margin: 0;
}

.stat-label {
  color: var(--muted);
  font-size: 0.92rem;
}

.stat-value {
  font-size: 1.6rem;
  font-weight: 700;
  margin-top: 10px;
}

.panel {
  margin-top: 18px;
}

.panel h2 {
  font-size: 1.3rem;
  margin-bottom: 14px;
}

.filters {
  margin-top: 22px;
}

.filter-row {
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
}

.filter-button {
  appearance: none;
  border: 1px solid var(--line);
  background: var(--surface-strong);
  color: var(--ink);
  padding: 12px 14px;
  border-radius: 999px;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  transition: 180ms ease;
}

.filter-button.active {
  background: var(--ink);
  color: #fff;
  border-color: var(--ink);
}

.filter-button:hover {
  transform: translateY(-1px);
}

.summary-grid {
  margin-top: 28px;
}

.summary-hero-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 16px;
  margin-top: 28px;
}

.summary-card {
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(215, 199, 180, 0.95);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow);
}

.summary-card strong {
  display: block;
  font-size: 0.9rem;
  color: var(--muted);
}

.summary-card .big-number {
  margin-top: 8px;
  font-size: 2rem;
  font-weight: 800;
}

.summary-card .summary-note {
  margin-top: 8px;
  color: var(--muted);
  font-size: 0.86rem;
}

.summary-card.ready .big-number {
  color: var(--accent);
}

.summary-card.caution .big-number {
  color: var(--warn);
}

.summary-card.unreliable .big-number {
  color: var(--danger);
}

.summary-card.shortage .big-number {
  color: var(--empty);
}

.list-grid {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.plain-list {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
}

.plain-list strong {
  color: var(--ink);
}

.card-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  margin-top: 22px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 28px;
}

.section-title-row h2 {
  margin: 0;
  font-size: 1.4rem;
}

.section-kicker {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 0.95rem;
}

.empty-zone {
  margin-top: 28px;
  padding: 20px;
  border-radius: 22px;
  border: 1px solid rgba(91, 33, 182, 0.18);
  background: linear-gradient(180deg, rgba(239, 228, 255, 0.92), rgba(248, 242, 255, 0.95));
  box-shadow: var(--shadow);
}

.empty-zone h2 {
  margin: 0;
}

.empty-zone p {
  margin: 8px 0 0;
  color: #5f3b9b;
}

.store-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.store-card[data-severity="critical"] {
  border-color: rgba(180, 35, 24, 0.35);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 226, 223, 0.78));
}

.store-card[data-severity="shortage"] {
  border-color: rgba(91, 33, 182, 0.28);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(239, 228, 255, 0.84));
}

.store-card[data-severity="caution"] {
  border-color: rgba(180, 83, 9, 0.35);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 241, 214, 0.86));
}

.store-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.store-title {
  margin: 0;
  font-size: 1.15rem;
}

.store-subtitle {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.badge-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1;
}

.badge.ok {
  color: var(--accent);
  background: var(--accent-soft);
}

.badge.warn {
  color: var(--warn);
  background: var(--warn-soft);
}

.badge.danger {
  color: var(--danger);
  background: var(--danger-soft);
}

.badge.empty {
  color: var(--empty);
  background: var(--empty-soft);
}

.warning-strip {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(180, 35, 24, 0.22);
  background: rgba(255, 226, 223, 0.72);
  color: #8e1c17;
  font-weight: 700;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric {
  padding: 12px;
  border: 1px solid rgba(215, 199, 180, 0.9);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
}

.metric-label {
  color: var(--muted);
  font-size: 0.82rem;
}

.metric-value {
  margin-top: 6px;
  font-size: 1.05rem;
  font-weight: 700;
}

.store-list,
.note-list {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
}

.store-list li + li,
.note-list li + li {
  margin-top: 6px;
}

.table-wrap {
  padding: 18px;
  margin-top: 28px;
  overflow: hidden;
}

.table-scroll {
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 980px;
}

thead th {
  text-align: left;
  font-size: 0.85rem;
  color: var(--muted);
  padding: 12px;
  border-bottom: 1px solid var(--line);
}

tbody td {
  padding: 12px;
  border-bottom: 1px solid rgba(215, 199, 180, 0.7);
  vertical-align: top;
}

tbody tr[data-severity="critical"] {
  background: rgba(255, 226, 223, 0.55);
}

tbody tr[data-severity="shortage"] {
  background: rgba(239, 228, 255, 0.55);
}

.footer {
  margin-top: 28px;
  color: var(--muted);
  font-size: 0.92rem;
  text-align: center;
}

@media (max-width: 720px) {
  .page {
    width: min(100% - 20px, 1200px);
    padding-top: 16px;
  }

  .hero,
  .panel,
  .stat,
  .store-card,
  .table-wrap {
    border-radius: 20px;
  }

  .hero {
    padding: 22px 18px;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .store-header {
    flex-direction: column;
  }

  .summary-hero-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 520px) {
  .summary-hero-grid {
    grid-template-columns: 1fr;
  }
}
"""

SITE_JS = """\
const FILTERS = {
  all: () => true,
  ready: (store) => store.filter_key === "ready",
  caution: (store) => store.filter_key === "caution" || store.filter_key === "reference",
  unreliable: (store) => store.filter_key === "unreliable",
  shortage: (store) => store.filter_key === "shortage",
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function badgeClass(status) {
  if (status === "データ不足") return "empty";
  if (status === "台番分析は信頼不可") return "danger";
  if (status === "台番分析は注意付き" || status === "台番分析は参考程度") return "warn";
  return "ok";
}

function fetchBadgeClass(status) {
  if (status === "partial_success") return "warn";
  if (status === "failed" || status === "失敗") return "danger";
  return "ok";
}

function parseBadgeClass(status) {
  if (status === "failed" || status === "失敗") return "empty";
  return "ok";
}

function renderBadge(text, extraClass = "") {
  return `<span class="badge ${extraClass}">${escapeHtml(text)}</span>`;
}

function renderList(items, emptyLabel = "なし") {
  if (!items || items.length === 0) {
    return `<li>${escapeHtml(emptyLabel)}</li>`;
  }
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderSummaryCard(label, value, note, kind) {
  return `
    <div class="summary-card ${escapeHtml(kind)}">
      <strong>${escapeHtml(label)}</strong>
      <div class="big-number">${escapeHtml(value)}</div>
      <div class="summary-note">${escapeHtml(note)}</div>
    </div>
  `;
}

function cardTemplate(store) {
  const fetchBadge = renderBadge(
    `取得:${store.fetch_status}`,
    fetchBadgeClass(store.fetch_status),
  );
  const parseBadge = renderBadge(
    `parse:${store.parse_status}`,
    parseBadgeClass(store.parse_status),
  );
  const statusBadge = renderBadge(
    store.pattern_analysis_status,
    badgeClass(store.pattern_analysis_status),
  );
  return `
    <article class="store-card" data-severity="${escapeHtml(store.severity_key)}">
      <div class="store-header">
        <div>
          <h3 class="store-title">${escapeHtml(store.display_name)}</h3>
          <p class="store-subtitle">${escapeHtml(store.store_id)}</p>
        </div>
        <div class="badge-group">
          ${fetchBadge}
          ${parseBadge}
          ${statusBadge}
        </div>
      </div>
      <div class="metric-grid">
        <div class="metric">
          <div class="metric-label">unit_diff_missing_rate</div>
          <div class="metric-value">${escapeHtml(store.unit_diff_missing_rate_text)}</div>
        </div>
        <div class="metric">
          <div class="metric-label">unit_results_total</div>
          <div class="metric-value">${escapeHtml(store.unit_results_total_text)}</div>
        </div>
        <div class="metric">
          <div class="metric-label">diff_null_count</div>
          <div class="metric-value">${escapeHtml(store.diff_null_count_text)}</div>
        </div>
        <div class="metric">
          <div class="metric-label">有効分析範囲</div>
          <div class="metric-value">${escapeHtml(store.effective_analyses_text)}</div>
        </div>
        <div class="metric">
          <div class="metric-label">failed_machine_pages</div>
          <div class="metric-value">${escapeHtml(store.failed_machine_pages || 0)}</div>
        </div>
      </div>
      <div>
        <strong>分析ステータス</strong>
        <ul class="store-list">
          <li>台番: ${escapeHtml(store.pattern_analysis_status)}</li>
          <li>末尾: ${escapeHtml(store.tail_analysis_status)}</li>
          <li>並び: ${escapeHtml(store.cluster_analysis_status)}</li>
        </ul>
      </div>
      <div>
        <strong>注意点</strong>
        <ul class="note-list">${renderList(store.notes, "追加注意なし")}</ul>
      </div>
      ${
        store.severity_key === "critical"
          ? `<div class="warning-strip">現時点では店舗別・機種別・カテゴリ別分析のみ有効</div>`
          : ""
      }
    </article>
  `;
}

function tableRowTemplate(store) {
  return `
    <tr data-severity="${escapeHtml(store.severity_key)}">
      <td>${escapeHtml(store.display_name)}</td>
      <td>${escapeHtml(store.fetch_status)}</td>
      <td>${escapeHtml(store.parse_status)}</td>
      <td>${escapeHtml(store.failed_machine_pages || 0)}</td>
      <td>${escapeHtml(store.unit_diff_missing_rate_text)}</td>
      <td>${escapeHtml(store.unit_results_total_text)}</td>
      <td>${escapeHtml(store.diff_null_count_text)}</td>
      <td>${escapeHtml(store.pattern_analysis_status)}</td>
      <td>${escapeHtml(store.tail_analysis_status)}</td>
      <td>${escapeHtml(store.cluster_analysis_status)}</td>
      <td>${escapeHtml(store.effective_analyses_text)}</td>
    </tr>
  `;
}

function mountDashboard(payload) {
  const root = document.getElementById("app");
  const filters = payload.filters || [];
  const stores = payload.stores || [];
  let activeFilter = "all";

  function filteredStores() {
    const predicate = FILTERS[activeFilter] || FILTERS.all;
    return stores.filter(predicate);
  }

  function render() {
    const visibleStores = filteredStores();
    const visibleShortageStores = visibleStores.filter(
      (store) => store.severity_key === "shortage",
    );
    const visibleActiveStores = visibleStores.filter(
      (store) => store.severity_key !== "shortage",
    );
    root.innerHTML = `
      <main class="page">
        <section class="hero">
          <p class="eyebrow">Slot Analyzer Dashboard</p>
          <h1>9店舗の unit coverage を一覧できる静的ダッシュボード</h1>
          <p>${escapeHtml(payload.description || "")}</p>
          <div class="hero-alert">
            <strong>現時点では店舗別・機種別・カテゴリ別分析のみ有効</strong>
            <p>欠損率が高い店舗では、台番・末尾・並び分析を有効に見せないよう固定しています。</p>
          </div>
          <div class="meta-grid">
            <div class="stat">
              <div class="stat-label">source</div>
              <div class="stat-value">${escapeHtml(payload.source || "-")}</div>
            </div>
            <div class="stat">
              <div class="stat-label">最終更新日時</div>
              <div class="stat-value">${escapeHtml(payload.generated_at || "-")}</div>
            </div>
            <div class="stat">
              <div class="stat-label">集計対象期間</div>
              <div class="stat-value">${escapeHtml(payload.coverage_window || "-")}</div>
            </div>
            <div class="stat">
              <div class="stat-label">表示店舗数</div>
              <div class="stat-value">${visibleStores.length} / ${stores.length}</div>
            </div>
          </div>
          <div class="summary-hero-grid">
            ${renderSummaryCard(
              "台番分析可能店舗数",
              payload.summary_counts.ready,
              "いまは 0 店舗でも一目で確認",
              "ready",
            )}
            ${renderSummaryCard(
              "注意付き店舗数",
              payload.summary_counts.caution,
              "注意付き・参考程度",
              "caution",
            )}
            ${renderSummaryCard(
              "信頼不可店舗数",
              payload.summary_counts.unreliable,
              "欠損率50%以上は赤系で強調",
              "unreliable",
            )}
            ${renderSummaryCard(
              "データ不足店舗数",
              payload.summary_counts.shortage,
              "別枠で確認が必要",
              "shortage",
            )}
          </div>
        </section>

        <section class="filters panel">
          <h2>フィルタ</h2>
          <div class="filter-row">
            ${filters
              .map(
                (filter) => `
                  <button
                    class="filter-button ${filter.key === activeFilter ? "active" : ""}"
                    data-filter="${escapeHtml(filter.key)}"
                    type="button"
                  >
                    ${escapeHtml(filter.label)}
                  </button>
                `
              )
              .join("")}
          </div>
        </section>

        <section class="summary-grid">
          <div class="panel">
            <h2>データ不足店舗</h2>
            <div class="list-grid">
              <ol class="plain-list">${renderList(payload.data_shortage_stores, "なし")}</ol>
            </div>
          </div>
          <div class="panel">
            <h2>明日の狙い候補</h2>
            <div class="list-grid">
              <ol class="plain-list">${renderList(payload.tomorrow_candidates, "候補なし")}</ol>
            </div>
          </div>
          <div class="panel">
            <h2>見送り推奨店舗</h2>
            <div class="list-grid">
              <ol class="plain-list">${renderList(payload.skip_recommendations, "該当なし")}</ol>
            </div>
          </div>
          <div class="panel">
            <h2>注意点</h2>
            <div class="list-grid">
              <ul class="plain-list">${renderList(payload.notes, "追加注意なし")}</ul>
            </div>
          </div>
        </section>

        ${
          visibleShortageStores.length
            ? `
              <section class="empty-zone">
                <h2>データ不足店舗</h2>
                <p>
                  この店舗群は unit_results サンプルが不足しているため、
                  台番・末尾・並び分析の対象外です。
                </p>
                <div class="card-grid">
                  ${visibleShortageStores.map(cardTemplate).join("")}
                </div>
              </section>
            `
            : ""
        }

        <section>
          <div class="section-title-row">
            <div>
              <h2>店舗カード</h2>
              <p class="section-kicker">信頼不可は赤系、データ不足は別枠で表示しています。</p>
            </div>
          </div>
          <div class="card-grid">
            ${visibleActiveStores.map(cardTemplate).join("")}
          </div>
        </section>

        <section class="table-wrap">
          <h2>9店舗比較テーブル</h2>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>店舗</th>
                  <th>取得</th>
                  <th>parse</th>
                  <th>machine失敗</th>
                  <th>欠損率</th>
                  <th>unit件数</th>
                  <th>diff NULL</th>
                  <th>台番</th>
                  <th>末尾</th>
                  <th>並び</th>
                  <th>有効分析範囲</th>
                </tr>
              </thead>
              <tbody>${visibleStores.map(tableRowTemplate).join("")}</tbody>
            </table>
          </div>
        </section>

        <p class="footer">raw HTML や SQLite DB は公開せず、summary JSON のみを出力しています。</p>
      </main>
    `;

    root.querySelectorAll("[data-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        activeFilter = button.getAttribute("data-filter") || "all";
        render();
      });
    });
  }

  render();
}

async function loadPayload() {
  try {
    const response = await fetch("./data/latest.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`latest.json load failed: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    if (window.__SITE_DATA__) {
      return window.__SITE_DATA__;
    }
    throw error;
  }
}

loadPayload()
  .then((payload) => mountDashboard(payload))
  .catch((error) => {
    const root = document.getElementById("app");
    root.innerHTML = [
      `<main class="page">`,
      `<section class="panel">`,
      `<h2>表示エラー</h2>`,
      `<p>${escapeHtml(error.message)}</p>`,
      `</section>`,
      `</main>`,
    ].join("");
  });
"""


def _coverage_window_text(target_date: date, lookback_days: int) -> str:
    start_date = target_date - timedelta(days=lookback_days)
    end_date = target_date - timedelta(days=1)
    return f"{start_date.isoformat()} 〜 {end_date.isoformat()}"


def _store_filter_key(status: str) -> str:
    if status == "データ不足":
        return "shortage"
    if status == "台番分析可能":
        return "ready"
    if status == "台番分析は信頼不可":
        return "unreliable"
    if status == "台番分析は参考程度":
        return "reference"
    return "caution"


def _store_severity_key(status: str) -> str:
    if status == "データ不足":
        return "shortage"
    if status == "台番分析は信頼不可":
        return "critical"
    if status in {"台番分析は注意付き", "台番分析は参考程度"}:
        return "caution"
    return "ready"


def _safe_text(value: object, empty: str = "データ不足") -> str:
    if value is None:
        return empty
    return str(value)


def _make_store_notes(
    *,
    fetch_status: str,
    parse_status: str,
    quality: dict[str, object],
    failed_machine_pages: int = 0,
    status_note: str = "",
) -> list[str]:
    notes: list[str] = []

    def add_note(note: str) -> None:
        if note and note not in notes:
            notes.append(note)

    if fetch_status not in {"成功", "success"}:
        add_note("取得状況は要確認")
    if fetch_status == "partial_success":
        add_note(f"一部機種ページ取得失敗: {failed_machine_pages}件")
    if parse_status not in {"成功", "success"}:
        add_note("parse済み unit_results が不足")
    if int(quality["total_rows"]) == 0:
        add_note("unit_results サンプルが 0 のためデータ不足")
    if float(quality["diff_missing_rate"]) >= 0.5:
        add_note("欠損率50%以上のため台番・末尾・並び分析は信頼不可")
    if status_note:
        add_note(status_note)
    return notes or ["大きな追加注意なし"]


def _store_payload(
    *,
    store,
    quality: dict[str, object],
    fetch_status: str,
    parse_status: str,
    failed_machine_pages: int = 0,
    status_note: str = "",
) -> dict[str, object]:
    filter_key = _store_filter_key(str(quality["pattern_analysis_status"]))
    severity_key = _store_severity_key(str(quality["pattern_analysis_status"]))
    excluded_machines = [
        f"{row['machine_name']} ({row['reason']})" for row in quality["excluded_machines"][:10]
    ]
    return {
        "store_id": store.store_id,
        "display_name": store.display_name,
        "fetch_status": fetch_status,
        "parse_status": parse_status,
        "failed_machine_pages": failed_machine_pages,
        "unit_diff_missing_rate": quality["diff_missing_rate"],
        "unit_diff_missing_rate_text": (
            "データ不足"
            if int(quality["total_rows"]) == 0
            else str(quality["diff_missing_rate"])
        ),
        "unit_results_total": quality["total_rows"],
        "unit_results_total_text": _safe_text(quality["total_rows"], "0"),
        "diff_null_count": quality["diff_null_count"],
        "diff_null_count_text": _safe_text(quality["diff_null_count"], "0"),
        "pattern_analysis_status": quality["pattern_analysis_status"],
        "tail_analysis_status": quality["tail_analysis_status"],
        "cluster_analysis_status": quality["cluster_analysis_status"],
        "effective_analyses": quality["effective_analyses"],
        "effective_analyses_text": (
            "データ不足"
            if int(quality["total_rows"]) == 0
            else ", ".join(quality["effective_analyses"])
        ),
        "excluded_machines": excluded_machines,
        "notes": _make_store_notes(
            fetch_status=fetch_status,
            parse_status=parse_status,
            quality=quality,
            failed_machine_pages=failed_machine_pages,
            status_note=status_note,
        ),
        "filter_key": filter_key,
        "severity_key": severity_key,
    }


def load_validation_statuses(report_path: Path) -> dict[str, dict[str, str]]:
    if not report_path.exists():
        return {}

    statuses: dict[str, dict[str, str]] = {}
    current_store: str | None = None
    for raw_line in report_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("| `") and line.count("|") >= 10:
            columns = [column.strip() for column in line.strip("|").split("|")]
            if not columns or columns[0] == "店舗ID" or columns[0].startswith("---"):
                continue
            store_id = columns[0].strip("`")
            if store_id:
                statuses[store_id] = {
                    "fetch_status": columns[1],
                    "parse_status": columns[2],
                }
                if len(columns) >= 4:
                    statuses[store_id]["failed_machine_pages"] = columns[3]
                if columns:
                    statuses[store_id]["status_note"] = columns[-1]
            continue
        if line.startswith("## "):
            current_store = line.removeprefix("## ").strip()
            statuses[current_store] = {}
            continue
        if current_store is None:
            continue
        if line.startswith("- 取得: "):
            statuses[current_store]["fetch_status"] = line.removeprefix("- 取得: ").strip()
        if line.startswith("- parse: "):
            statuses[current_store]["parse_status"] = line.removeprefix("- parse: ").strip()
        if line.startswith("- failed_machine_pages: "):
            statuses[current_store]["failed_machine_pages"] = (
                line.removeprefix("- failed_machine_pages: ").strip()
            )
        if line.startswith("- 注意点: "):
            statuses[current_store]["status_note"] = line.removeprefix("- 注意点: ").strip()
    return statuses


def _build_summary_payload(
    *,
    database,
    store_normalizer,
    target_date: date,
    lookback_days: int,
    source: str | None = None,
    status_overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, object]:
    analysis = run_analysis(
        database,
        store_normalizer,
        target_date,
        lookback_days,
        source=source,
    )
    rows_by_store = {row["store_id"]: row for row in analysis["rows"]}
    stores_payload: list[dict[str, object]] = []

    for store in store_normalizer.list_stores():
        row = rows_by_store[store.store_id]
        quality = row["unit_quality"]
        fetch_status = (
            "成功" if row["sample_size"] > 0 or int(quality["total_rows"]) > 0 else "失敗"
        )
        parse_status = "成功" if int(quality["total_rows"]) > 0 else "失敗"
        override = (status_overrides or {}).get(
            store.store_id,
            (status_overrides or {}).get(store.display_name, {}),
        )
        failed_machine_pages = int(override.get("failed_machine_pages", "0") or "0")
        stores_payload.append(
            _store_payload(
                store=store,
                quality=quality,
                fetch_status=override.get("fetch_status", fetch_status),
                parse_status=override.get("parse_status", parse_status),
                failed_machine_pages=failed_machine_pages,
                status_note=override.get("status_note", ""),
            )
        )

    data_shortage_stores = [
        store["display_name"]
        for store in stores_payload
        if store["pattern_analysis_status"] == "データ不足"
    ]
    tomorrow_candidates = [
        (
            f"{row['display_name']} (score={row['score']}, "
            f"信頼度={row['confidence']}, sample={row['sample_size']})"
        )
        for row in analysis["rows"][:5]
    ]
    skip_recommendations = [
        f"{row['display_name']} ({row['avoid_reason'] or '明確な根拠不足'})"
        for row in analysis["rows"]
        if row["confidence"] == "D"
    ]
    notes = [
        f"表示 source は {source or 'all'} です。",
        "machine_results から unit_results を推定で補完していません。",
        "差枚 '-' は 0 として扱わず、NULL と 0 を区別しています。",
        "欠損率が高い店舗では台番・末尾・並び分析を有効表示していません。",
    ]
    summary_counts = {"ready": 0, "caution": 0, "unreliable": 0, "shortage": 0}
    for store in stores_payload:
        key = str(store["filter_key"])
        if key in summary_counts:
            summary_counts[key] += 1

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_date": target_date.isoformat(),
        "source": source or "all",
        "lookback_days": lookback_days,
        "coverage_window": analysis.get(
            "coverage_window",
            _coverage_window_text(target_date, lookback_days),
        ),
        "description": (
            f"9店舗の unit coverage・取得状況・明日の狙い候補を 1 画面で確認できます。"
            f" source={source or 'all'}"
        ),
        "filters": [
            {"key": "all", "label": "全店舗"},
            {"key": "ready", "label": "台番分析可能"},
            {"key": "caution", "label": "注意付き"},
            {"key": "unreliable", "label": "信頼不可"},
            {"key": "shortage", "label": "データ不足"},
        ],
        "stores": stores_payload,
        "data_shortage_stores": data_shortage_stores,
        "tomorrow_candidates": tomorrow_candidates,
        "skip_recommendations": skip_recommendations,
        "notes": notes,
        "summary_counts": summary_counts,
    }


def _index_html(payload: dict[str, object]) -> str:
    return """\
<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Slot Analyzer Dashboard</title>
    <link rel="stylesheet" href="./assets/style.css">
  </head>
  <body>
    <div id="app"></div>
    <script src="./assets/app.js"></script>
  </body>
</html>
"""


def build_static_site(
    *,
    database,
    store_normalizer,
    target_date: date,
    lookback_days: int,
    output_dir: Path,
    source: str | None = None,
    status_overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, Path]:
    payload = _build_summary_payload(
        database=database,
        store_normalizer=store_normalizer,
        target_date=target_date,
        lookback_days=lookback_days,
        source=source,
        status_overrides=status_overrides,
    )
    data_dir = output_dir / "data"
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "index.html"
    data_path = data_dir / "latest.json"
    style_path = assets_dir / "style.css"
    app_path = assets_dir / "app.js"

    index_path.write_text(_index_html(payload), encoding="utf-8")
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    style_path.write_text(SITE_CSS, encoding="utf-8")
    app_path.write_text(SITE_JS, encoding="utf-8")

    return {
        "index": index_path,
        "data": data_path,
        "style": style_path,
        "app": app_path,
    }

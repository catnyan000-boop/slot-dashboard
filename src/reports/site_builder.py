from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from src.reports.tomorrow_report import run_analysis

SITE_CSS = """\
:root {
  --bg: #f6f1e8;
  --surface: rgba(255, 252, 247, 0.94);
  --surface-strong: #ffffff;
  --ink: #1f1d1a;
  --muted: #6a6258;
  --line: rgba(122, 108, 90, 0.18);
  --shadow: 0 22px 48px rgba(67, 48, 22, 0.08);
  --grade-a: #165f55;
  --grade-a-soft: #dff6f0;
  --grade-b: #a15b00;
  --grade-b-soft: #fff1d9;
  --grade-c: #9f2d2d;
  --grade-c-soft: #ffe3e0;
  --grade-calm: #e7ddd0;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(22, 95, 85, 0.12), transparent 28%),
    linear-gradient(180deg, #f9f4ec 0%, #f2e8da 100%);
}

button,
summary {
  font: inherit;
}

.page {
  width: min(1180px, calc(100% - 28px));
  margin: 0 auto;
  padding: 18px 0 40px;
}

.hero,
.panel,
.group-panel,
.store-card,
.table-panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 26px;
  box-shadow: var(--shadow);
}

.hero {
  padding: 24px;
  background:
    linear-gradient(150deg, rgba(255, 255, 255, 0.98), rgba(245, 236, 224, 0.92));
}

.eyebrow {
  margin: 0;
  color: var(--grade-a);
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-title {
  margin: 10px 0 0;
  font-size: clamp(2rem, 4vw, 3.6rem);
  line-height: 1.02;
}

.hero-copy {
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 1rem;
  max-width: 72ch;
}

.decision-card {
  margin-top: 20px;
  padding: 22px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(22, 95, 85, 0.95), rgba(27, 43, 40, 0.92));
  color: #f8f5ef;
}

.decision-kicker {
  margin: 0;
  font-size: 0.9rem;
  opacity: 0.85;
}

.decision-title {
  margin: 8px 0 0;
  font-size: clamp(1.4rem, 3vw, 2.2rem);
  line-height: 1.2;
}

.decision-copy {
  margin: 12px 0 0;
  font-size: 1.02rem;
  line-height: 1.6;
  max-width: 68ch;
}

.meta-grid,
.summary-grid,
.filter-row,
.group-grid,
.detail-grid {
  display: grid;
  gap: 14px;
}

.meta-grid {
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  margin-top: 18px;
}

.summary-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-top: 18px;
}

.meta-card,
.summary-card {
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.82);
}

.meta-label,
.summary-label {
  color: var(--muted);
  font-size: 0.82rem;
}

.meta-value,
.summary-value {
  margin-top: 8px;
  font-size: 1.2rem;
  font-weight: 800;
}

.summary-note {
  margin-top: 8px;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.4;
}

.summary-card.a .summary-value,
.badge.grade-a,
.store-card[data-grade="A"] .decision-mark {
  color: var(--grade-a);
}

.summary-card.b .summary-value,
.badge.grade-b,
.store-card[data-grade="B"] .decision-mark {
  color: var(--grade-b);
}

.summary-card.c .summary-value,
.badge.grade-c,
.store-card[data-grade="C"] .decision-mark {
  color: var(--grade-c);
}

.panel,
.group-panel,
.table-panel {
  margin-top: 20px;
  padding: 18px;
}

.panel h2,
.group-head h2,
.table-panel h2 {
  margin: 0;
  font-size: 1.24rem;
}

.panel-copy,
.group-copy,
.table-copy {
  margin: 8px 0 0;
  color: var(--muted);
  line-height: 1.5;
}

.filter-row {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  margin-top: 14px;
}

.filter-button {
  appearance: none;
  border: 1px solid var(--line);
  background: var(--surface-strong);
  color: var(--ink);
  padding: 12px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 800;
  transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
}

.filter-button.active {
  border-color: transparent;
  background: var(--ink);
  color: #fff;
}

.filter-button:hover {
  transform: translateY(-1px);
}

.group-panel[data-grade="A"] {
  border-color: rgba(22, 95, 85, 0.18);
}

.group-panel[data-grade="B"] {
  border-color: rgba(161, 91, 0, 0.2);
  background: linear-gradient(180deg, rgba(255, 252, 247, 0.96), rgba(255, 247, 230, 0.94));
}

.group-panel[data-grade="C"] {
  border-color: rgba(159, 45, 45, 0.2);
  background: linear-gradient(180deg, rgba(255, 252, 247, 0.96), rgba(255, 235, 232, 0.94));
}

.group-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.group-count {
  min-width: 70px;
  padding: 10px 12px;
  border-radius: 18px;
  text-align: center;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid var(--line);
}

.group-count strong {
  display: block;
  font-size: 1.3rem;
}

.group-grid {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  margin-top: 18px;
}

.empty-note {
  margin: 18px 0 0;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--muted);
}

.store-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.store-card[data-grade="A"] {
  border-color: rgba(22, 95, 85, 0.18);
}

.store-card[data-grade="B"] {
  border-color: rgba(161, 91, 0, 0.24);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 246, 225, 0.9));
}

.store-card[data-grade="C"] {
  border-color: rgba(159, 45, 45, 0.24);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 235, 232, 0.92));
}

.store-top {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.store-title {
  margin: 0;
  font-size: 1.15rem;
}

.store-id {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 0.88rem;
}

.badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 0.76rem;
  font-weight: 800;
  line-height: 1;
}

.badge.grade-a,
.badge.ok {
  background: var(--grade-a-soft);
}

.badge.grade-b,
.badge.warn {
  background: var(--grade-b-soft);
}

.badge.grade-c,
.badge.danger {
  background: var(--grade-c-soft);
}

.badge.neutral {
  background: #f1ece5;
  color: #5a5249;
}

.decision-mark {
  font-size: 2.2rem;
  font-weight: 900;
  line-height: 1;
}

.decision-state {
  display: flex;
  align-items: center;
  gap: 12px;
}

.decision-copy-short {
  color: var(--muted);
  line-height: 1.5;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.status-tile {
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--line);
}

.status-label {
  color: var(--muted);
  font-size: 0.8rem;
}

.status-value {
  margin-top: 6px;
  font-weight: 800;
  line-height: 1.4;
}

.reason-box {
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--line);
}

.reason-box strong {
  display: block;
  margin-bottom: 8px;
}

.reason-box p,
.detail-grid p {
  margin: 0;
  line-height: 1.5;
  color: var(--muted);
}

.detail-box {
  border-top: 1px solid var(--line);
  padding-top: 12px;
}

.detail-box summary {
  cursor: pointer;
  font-weight: 800;
  list-style: none;
}

.detail-box summary::-webkit-details-marker {
  display: none;
}

.detail-box summary::after {
  content: "＋";
  margin-left: 8px;
}

.detail-box[open] summary::after {
  content: "−";
}

.detail-grid {
  margin-top: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-item {
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--line);
}

.detail-item strong {
  display: block;
  margin-bottom: 6px;
}

.detail-list {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
}

.detail-list li + li {
  margin-top: 4px;
}

.table-panel details {
  margin-top: 12px;
}

.table-panel summary {
  cursor: pointer;
  font-weight: 800;
}

.table-scroll {
  overflow: auto;
  margin-top: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

thead th {
  text-align: left;
  padding: 12px;
  color: var(--muted);
  font-size: 0.82rem;
  border-bottom: 1px solid var(--line);
}

tbody td {
  padding: 12px;
  border-bottom: 1px solid rgba(122, 108, 90, 0.14);
  vertical-align: top;
}

.footer {
  margin-top: 24px;
  color: var(--muted);
  font-size: 0.88rem;
  text-align: center;
}

@media (max-width: 720px) {
  .page {
    width: min(100% - 18px, 1180px);
    padding-top: 14px;
  }

  .hero,
  .panel,
  .group-panel,
  .store-card,
  .table-panel {
    border-radius: 20px;
  }

  .hero,
  .panel,
  .group-panel,
  .table-panel {
    padding: 16px;
  }

  .decision-card {
    padding: 18px;
  }

  .group-head,
  .store-top,
  .decision-state {
    flex-direction: column;
  }

  .badge-row {
    justify-content: flex-start;
  }

  .status-grid,
  .detail-grid,
  .summary-grid,
  .meta-grid,
  .group-grid {
    grid-template-columns: 1fr;
  }
}
"""

SITE_JS = """\
const FILTERS = {
  all: () => true,
  grade_a: (store) => store.decision_grade === "A",
  grade_b: (store) => store.decision_grade === "B",
  grade_c: (store) => store.decision_grade === "C",
  partial_success: (store) => store.fetch_status === "partial_success",
  shortage: (store) => Number(store.unit_results_total || 0) === 0,
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderBadge(text, kind = "neutral") {
  return `<span class="badge ${escapeHtml(kind)}">${escapeHtml(text)}</span>`;
}

function renderList(items, emptyLabel = "なし") {
  if (!items || items.length === 0) {
    return `<li>${escapeHtml(emptyLabel)}</li>`;
  }
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function gradeBadgeKind(grade) {
  if (grade === "A") return "grade-a";
  if (grade === "B") return "grade-b";
  return "grade-c";
}

function stateBadgeKind(grade) {
  if (grade === "A") return "ok";
  if (grade === "B") return "warn";
  return "danger";
}

function fetchStatusText(status) {
  if (status === "success") return "success";
  if (status === "partial_success") return "partial_success";
  return "failed";
}

function groupedStores(stores) {
  return {
    A: stores.filter((store) => store.decision_grade === "A"),
    B: stores.filter((store) => store.decision_grade === "B"),
    C: stores.filter((store) => store.decision_grade === "C"),
  };
}

function renderHeroCard(payload, stores) {
  const counts = payload.decision_counts || {};
  return `
    <section class="hero">
      <p class="eyebrow">Source ${escapeHtml(payload.source || "-")}</p>
      <h1 class="hero-title">今日どう判断するかを最初に見る画面</h1>
      <p class="hero-copy">${escapeHtml(payload.description || "")}</p>
      <div class="decision-card">
        <p class="decision-kicker">今日の全体判定</p>
        <h2 class="decision-title">
          全体として ${counts.shortage ? "一部見送りあり" : "利用可能"}
        </h2>
        <p class="decision-copy">${escapeHtml(payload.today_conclusion || "")}</p>
      </div>
      <div class="meta-grid">
        <div class="meta-card">
          <div class="meta-label">データソース</div>
          <div class="meta-value">${escapeHtml(payload.source || "-")}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">最終更新日時</div>
          <div class="meta-value">${escapeHtml(payload.generated_at || "-")}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">集計対象期間</div>
          <div class="meta-value">${escapeHtml(payload.coverage_window || "-")}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">対象店舗数</div>
          <div class="meta-value">${stores.length}店舗</div>
        </div>
      </div>
      <div class="summary-grid">
        <div class="summary-card a">
          <div class="summary-label">台番分析可能店舗数</div>
          <div class="summary-value">${escapeHtml(counts.analysis_ready || 0)}</div>
          <div class="summary-note">今日の判断に使える店舗数</div>
        </div>
        <div class="summary-card b">
          <div class="summary-label">注意付き店舗数</div>
          <div class="summary-value">${escapeHtml(counts.B || 0)}</div>
          <div class="summary-note">一部機種取得失敗あり</div>
        </div>
        <div class="summary-card c">
          <div class="summary-label">データ不足店舗数</div>
          <div class="summary-value">${escapeHtml(counts.shortage || 0)}</div>
          <div class="summary-note">今日の判断には使わない</div>
        </div>
        <div class="summary-card a">
          <div class="summary-label">A / B / C</div>
          <div class="summary-value">
            ${escapeHtml(`${counts.A || 0} / ${counts.B || 0} / ${counts.C || 0}`)}
          </div>
          <div class="summary-note">通常 / 注意付き / 見送り</div>
        </div>
      </div>
    </section>
  `;
}

function cardTemplate(store) {
  const failedText = Number(store.failed_machine_pages || 0) > 0
    ? `${store.failed_machine_pages}件`
    : "なし";
  const failedUrls = store.failed_machine_urls || [];
  return `
    <article class="store-card" data-grade="${escapeHtml(store.decision_grade)}">
      <div class="store-top">
        <div>
          <h3 class="store-title">${escapeHtml(store.display_name)}</h3>
          <p class="store-id">${escapeHtml(store.store_id)}</p>
        </div>
        <div class="badge-row">
          ${renderBadge(`判定 ${store.decision_grade}`, gradeBadgeKind(store.decision_grade))}
          ${renderBadge(store.decision_state, stateBadgeKind(store.decision_grade))}
          ${renderBadge(
            `台番分析 ${store.analysis_availability_text}`,
            stateBadgeKind(store.decision_grade),
          )}
        </div>
      </div>
      <div class="decision-state">
        <div class="decision-mark">${escapeHtml(store.decision_grade)}</div>
        <div class="decision-copy-short">${escapeHtml(store.decision_reason || "")}</div>
      </div>
      <div class="status-grid">
        <div class="status-tile">
          <div class="status-label">状態</div>
          <div class="status-value">${escapeHtml(store.decision_state)}</div>
        </div>
        <div class="status-tile">
          <div class="status-label">台番差枚</div>
          <div class="status-value">${escapeHtml(store.diff_status_text)}</div>
        </div>
        <div class="status-tile">
          <div class="status-label">unit_diff_missing_rate</div>
          <div class="status-value">${escapeHtml(store.unit_diff_missing_rate_text)}</div>
        </div>
        <div class="status-tile">
          <div class="status-label">failed_machine_pages</div>
          <div class="status-value">${escapeHtml(failedText)}</div>
        </div>
      </div>
      <div class="reason-box">
        <strong>注意理由</strong>
        <p>${escapeHtml((store.notes || [store.decision_reason])[0] || "追加注意なし")}</p>
      </div>
      <details class="detail-box">
        <summary>詳細を開く</summary>
        <div class="detail-grid">
          <div class="detail-item">
            <strong>件数</strong>
            <p>
              daily ${escapeHtml(store.daily_count || 0)} /
              machine ${escapeHtml(store.machine_count || 0)} /
              unit ${escapeHtml(store.unit_count || 0)}
            </p>
          </div>
          <div class="detail-item">
            <strong>取得状態</strong>
            <p>fetch_status: ${escapeHtml(fetchStatusText(store.fetch_status))}</p>
            <p>parse_status: ${escapeHtml(store.parse_status)}</p>
          </div>
          <div class="detail-item">
            <strong>有効分析範囲</strong>
            <p>${escapeHtml(store.effective_analyses_text)}</p>
          </div>
          <div class="detail-item">
            <strong>failed_machine_urls</strong>
            ${
              failedUrls.length
                ? `<ul class="detail-list">${renderList(failedUrls)}</ul>`
                : `<p>記録なし</p>`
            }
          </div>
          <div class="detail-item">
            <strong>注意点</strong>
            <ul class="detail-list">${renderList(store.notes, "追加注意なし")}</ul>
          </div>
        </div>
      </details>
    </article>
  `;
}

function groupSection(grade, title, copy, stores) {
  return `
    <section class="group-panel" data-grade="${escapeHtml(grade)}">
      <div class="group-head">
        <div>
          <h2>${escapeHtml(title)}</h2>
          <p class="group-copy">${escapeHtml(copy)}</p>
        </div>
        <div class="group-count">
          <strong>${stores.length}</strong>
          <span>店舗</span>
        </div>
      </div>
      ${
        stores.length
          ? `<div class="group-grid">${stores.map(cardTemplate).join("")}</div>`
          : `<div class="empty-note">該当店舗はありません。</div>`
      }
    </section>
  `;
}

function tableRowTemplate(store) {
  return `
    <tr>
      <td>${escapeHtml(store.display_name)}</td>
      <td>${escapeHtml(store.decision_grade)}</td>
      <td>${escapeHtml(fetchStatusText(store.fetch_status))}</td>
      <td>${escapeHtml(store.unit_count || 0)}</td>
      <td>${escapeHtml(store.unit_diff_missing_rate_text)}</td>
      <td>${escapeHtml((store.notes || [store.decision_reason])[0] || "追加注意なし")}</td>
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
    const groups = groupedStores(visibleStores);

    root.innerHTML = `
      <main class="page">
        ${renderHeroCard(payload, stores)}

        <section class="panel">
          <h2>店舗フィルタ</h2>
          <p class="panel-copy">
            まずは A / B / C で見て、必要なときだけ partial_success やデータ不足を確認します。
          </p>
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
                `,
              )
              .join("")}
          </div>
        </section>

        ${groupSection(
          "A",
          "A 通常利用可能",
          "fetch 成功、欠損率が低く、そのまま判断に使える店舗です。",
          groups.A,
        )}
        ${groupSection(
          "B",
          "B 注意付きで利用可能",
          "一部機種ページ取得失敗はあるものの、台番判断には使える店舗です。",
          groups.B,
        )}
        ${groupSection(
          "C",
          "C 見送り / データ不足",
          "欠損率や取得状態の都合で、今日の判断材料としては弱い店舗です。",
          groups.C,
        )}

        <section class="table-panel">
          <h2>比較テーブル</h2>
          <p class="table-copy">カードで判断したあとに、必要なら比較だけ確認します。</p>
          <details>
            <summary>比較テーブルを開く</summary>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>店舗</th>
                    <th>判定</th>
                    <th>fetch_status</th>
                    <th>unit件数</th>
                    <th>欠損率</th>
                    <th>注意点</th>
                  </tr>
                </thead>
                <tbody>${visibleStores.map(tableRowTemplate).join("")}</tbody>
              </table>
            </div>
          </details>
        </section>

        <p class="footer">
          source=${escapeHtml(payload.source || "-")} / raw HTML や SQLite DB は公開していません。
        </p>
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


def _normalize_fetch_status(status: str) -> str:
    value = status.strip()
    if value in {"success", "partial_success", "failed"}:
        return value
    if value == "成功":
        return "success"
    if value == "失敗":
        return "failed"
    if value == "失敗（前回データ使用）":
        return "failed"
    return value or "failed"


def _normalize_parse_status(status: str) -> str:
    value = status.strip()
    if value in {"success", "failed"}:
        return value
    if value == "成功":
        return "success"
    if value == "失敗":
        return "failed"
    return value or "failed"


def _decision_grade(
    *,
    fetch_status: str,
    total_rows: int,
    diff_missing_rate: float,
    pattern_status: str,
) -> str:
    if (
        fetch_status == "success"
        and total_rows > 0
        and diff_missing_rate < 0.1
        and pattern_status == "台番分析可能"
    ):
        return "A"
    if (
        fetch_status == "partial_success"
        and total_rows > 0
        and diff_missing_rate < 0.1
        and pattern_status == "台番分析可能"
    ):
        return "B"
    return "C"


def _decision_state_text(grade: str, total_rows: int) -> str:
    if grade == "A":
        return "通常利用可能"
    if grade == "B":
        return "注意付きで利用可能"
    if total_rows == 0:
        return "データ不足"
    return "見送り"


def _decision_reason_text(
    *,
    grade: str,
    fetch_status: str,
    total_rows: int,
    diff_missing_rate: float,
    failed_machine_pages: int,
) -> str:
    if grade == "A":
        return "通常どおり判断に使える"
    if grade == "B":
        return (
            "一部機種ページの取得に失敗。ただし台番データは取得できているため注意付きで利用可能"
        )
    if fetch_status == "failed" or total_rows == 0:
        return "データ不足。今日の判断には使わない"
    if diff_missing_rate >= 0.5:
        return "欠損率が高いため今日の判断には使わない"
    if failed_machine_pages > 0:
        return "取得失敗が混在しているため今日は見送り"
    return "判断材料が足りないため今日は見送り"


def _store_filter_key(grade: str, total_rows: int) -> str:
    if total_rows == 0:
        return "shortage"
    return {"A": "grade_a", "B": "grade_b"}.get(grade, "grade_c")


def _store_severity_key(grade: str, total_rows: int) -> str:
    if total_rows == 0:
        return "shortage"
    return {"A": "grade_a", "B": "grade_b"}.get(grade, "grade_c")


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
    decision_reason: str = "",
) -> list[str]:
    notes: list[str] = []

    def add_note(note: str) -> None:
        if note and note not in notes:
            notes.append(note)

    if decision_reason:
        add_note(decision_reason)
    if fetch_status == "partial_success":
        add_note(f"一部機種ページ取得失敗: {failed_machine_pages}件")
    if parse_status not in {"成功", "success"}:
        add_note("parse済み unit_results が不足")
    if int(quality["total_rows"]) == 0:
        add_note("unit_results サンプルが 0 のためデータ不足")
    if int(quality["total_rows"]) > 0 and float(quality["diff_missing_rate"]) == 0.0:
        add_note("台番差枚データ欠損なし")
    elif int(quality["total_rows"]) > 0:
        add_note(f"台番差枚データ欠損率 {quality['diff_missing_rate']}")
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
    daily_count: int = 0,
    machine_count: int = 0,
    failed_machine_urls: list[str] | None = None,
) -> dict[str, object]:
    total_rows = int(quality["total_rows"])
    diff_missing_rate = float(quality["diff_missing_rate"])
    normalized_fetch_status = _normalize_fetch_status(fetch_status)
    normalized_parse_status = _normalize_parse_status(parse_status)
    decision_grade = _decision_grade(
        fetch_status=normalized_fetch_status,
        total_rows=total_rows,
        diff_missing_rate=diff_missing_rate,
        pattern_status=str(quality["pattern_analysis_status"]),
    )
    decision_state = _decision_state_text(decision_grade, total_rows)
    decision_reason = _decision_reason_text(
        grade=decision_grade,
        fetch_status=normalized_fetch_status,
        total_rows=total_rows,
        diff_missing_rate=diff_missing_rate,
        failed_machine_pages=failed_machine_pages,
    )
    filter_key = _store_filter_key(decision_grade, total_rows)
    severity_key = _store_severity_key(decision_grade, total_rows)
    excluded_machines = [
        f"{row['machine_name']} ({row['reason']})" for row in quality["excluded_machines"][:10]
    ]
    return {
        "store_id": store.store_id,
        "display_name": store.display_name,
        "fetch_status": normalized_fetch_status,
        "parse_status": normalized_parse_status,
        "failed_machine_pages": failed_machine_pages,
        "failed_machine_urls": failed_machine_urls or [],
        "daily_count": daily_count,
        "machine_count": machine_count,
        "unit_count": total_rows,
        "decision_grade": decision_grade,
        "decision_state": decision_state,
        "decision_reason": decision_reason,
        "analysis_availability_text": (
            "可能" if str(quality["pattern_analysis_status"]) == "台番分析可能" else "不可"
        ),
        "unit_diff_missing_rate": quality["diff_missing_rate"],
        "unit_diff_missing_rate_text": (
            "データ不足"
            if total_rows == 0
            else str(quality["diff_missing_rate"])
        ),
        "diff_status_text": (
            "データ不足"
            if total_rows == 0
            else "台番差枚データ欠損なし"
            if diff_missing_rate == 0.0
            else f"台番差枚データ欠損率 {quality['diff_missing_rate']}"
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
            fetch_status=normalized_fetch_status,
            parse_status=normalized_parse_status,
            quality=quality,
            failed_machine_pages=failed_machine_pages,
            status_note=status_note,
            decision_reason=decision_reason,
        ),
        "filter_key": filter_key,
        "severity_key": severity_key,
    }


def _query_store_counts(
    database,
    *,
    store_id: str,
    target_date: date,
    lookback_days: int,
    source: str | None,
) -> dict[str, int]:
    start_date = (target_date - timedelta(days=lookback_days)).isoformat()
    end_date = target_date.isoformat()
    counts: dict[str, int] = {}
    for table_name, key in (
        ("daily_store_results", "daily"),
        ("machine_results", "machine"),
        ("unit_results", "unit"),
    ):
        sql = f"""
        SELECT COUNT(*) AS count
        FROM {table_name}
        WHERE store_id = ?
          AND report_date >= ?
          AND report_date < ?
        """
        params: list[str] = [store_id, start_date, end_date]
        if source:
            sql += "\n          AND source = ?"
            params.append(source)
        frame = database.query_dataframe(sql, params)
        counts[key] = int(frame.iloc[0]["count"]) if not frame.empty else 0
    return counts


def _overall_conclusion_text(stores_payload: list[dict[str, object]]) -> str:
    total = len(stores_payload)
    analysis_ready = sum(
        1 for store in stores_payload if store["pattern_analysis_status"] == "台番分析可能"
    )
    grade_b = sum(1 for store in stores_payload if store["decision_grade"] == "B")
    shortage = sum(1 for store in stores_payload if int(store["unit_results_total"]) == 0)
    parts = [f"{total}店舗中{analysis_ready}店舗で台番分析可能。"]
    if grade_b:
        parts.append(f"{grade_b}店舗は一部機種取得失敗あり。")
    if shortage:
        parts.append(f"{shortage}店舗はデータ不足。")
        parts.append("全体として一部見送り。")
    else:
        parts.append("全体として利用可能。")
    return "".join(parts)


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
        counts = _query_store_counts(
            database,
            store_id=store.store_id,
            target_date=target_date,
            lookback_days=lookback_days,
            source=source,
        )
        stores_payload.append(
            _store_payload(
                store=store,
                quality=quality,
                fetch_status=override.get("fetch_status", fetch_status),
                parse_status=override.get("parse_status", parse_status),
                failed_machine_pages=failed_machine_pages,
                status_note=override.get("status_note", ""),
                daily_count=counts["daily"],
                machine_count=counts["machine"],
                failed_machine_urls=override.get("failed_machine_urls", []),
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
        if key == "grade_a":
            summary_counts["ready"] += 1
        elif key == "grade_b":
            summary_counts["caution"] += 1
        elif key == "shortage":
            summary_counts["shortage"] += 1
        else:
            summary_counts["unreliable"] += 1

    decision_counts = {
        "A": sum(1 for store in stores_payload if store["decision_grade"] == "A"),
        "B": sum(1 for store in stores_payload if store["decision_grade"] == "B"),
        "C": sum(1 for store in stores_payload if store["decision_grade"] == "C"),
        "partial_success": sum(
            1 for store in stores_payload if store["fetch_status"] == "partial_success"
        ),
        "shortage": sum(1 for store in stores_payload if int(store["unit_results_total"]) == 0),
        "analysis_ready": sum(
            1 for store in stores_payload if store["pattern_analysis_status"] == "台番分析可能"
        ),
    }

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
            "最初に今日の判断を出し、その下に店舗ごとの使い方を並べています。"
        ),
        "filters": [
            {"key": "all", "label": "全店舗"},
            {"key": "grade_a", "label": "A 通常利用可能"},
            {"key": "grade_b", "label": "B 注意付き"},
            {"key": "grade_c", "label": "C 見送り"},
            {"key": "partial_success", "label": "partial_success"},
            {"key": "shortage", "label": "データ不足"},
        ],
        "stores": stores_payload,
        "data_shortage_stores": data_shortage_stores,
        "tomorrow_candidates": tomorrow_candidates,
        "skip_recommendations": skip_recommendations,
        "notes": notes,
        "summary_counts": summary_counts,
        "decision_counts": decision_counts,
        "today_conclusion": _overall_conclusion_text(stores_payload),
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

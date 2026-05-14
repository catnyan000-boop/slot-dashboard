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

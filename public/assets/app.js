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

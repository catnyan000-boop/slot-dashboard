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

function overallActionText(counts, total) {
  const available = Number(counts.A || 0) + Number(counts.B || 0);
  if (available === total && total > 0) {
    return "今日は全店舗を候補として見てよい。";
  }
  if (Number(counts.A || 0) > 0) {
    return "まず A 店舗を見て、B 店舗は注意付きで確認。";
  }
  if (Number(counts.B || 0) > 0) {
    return "A 判定なし。B 店舗だけ注意付きで確認。";
  }
  return "今日は見送り店舗が多いため慎重に判断。";
}

function targetTypeLabel(targetType) {
  if (targetType === "machine_candidate") return "狙い機種";
  if (targetType === "raise_candidate") return "上げ狙い";
  if (targetType === "keep_candidate") return "据え置き";
  if (targetType === "tail_candidate") return "末尾";
  if (targetType === "cluster_candidate") return "並び";
  return targetType;
}

function candidatePrimaryLabel(candidate) {
  if (candidate.machine_name && candidate.unit_number) {
    return `${candidate.machine_name} / ${candidate.unit_number}`;
  }
  return candidate.machine_name || candidate.unit_number || "-";
}

function candidateItem(candidate) {
  const evidence = candidate.evidence || {};
  return `
    <li>
      <strong>${escapeHtml(candidate.store_name)}</strong>
      <span class="candidate-meta">
        ${escapeHtml(candidatePrimaryLabel(candidate))} /
        ${escapeHtml(targetTypeLabel(candidate.target_type))} /
        score ${escapeHtml(candidate.score)} /
        confidence ${escapeHtml(candidate.confidence)}
      </span>
      <span class="candidate-meta">${escapeHtml(candidate.reason || "")}</span>
      <span class="candidate-meta">
        根拠:
        prev_diff=${escapeHtml(evidence.previous_day_diff ?? "-")} /
        prev_games=${escapeHtml(evidence.previous_day_games ?? "-")} /
        sample=${escapeHtml(evidence.sample_count ?? "-")}
      </span>
      ${
        candidate.caution
          ? `<span class="candidate-meta">注意: ${escapeHtml(candidate.caution)}</span>`
          : ""
      }
    </li>
  `;
}

function renderCandidateList(title, copy, candidates, emptyLabel) {
  return `
    <div class="target-card">
      <h3>${escapeHtml(title)}</h3>
      <p class="target-copy">${escapeHtml(copy)}</p>
      ${
        candidates && candidates.length
          ? `<ul class="candidate-list">${candidates.map(candidateItem).join("")}</ul>`
          : `<p class="target-copy">${escapeHtml(emptyLabel)}</p>`
      }
    </div>
  `;
}

function renderHeroCard(payload, groups) {
  const counts = payload.decision_counts || {};
  const total = (payload.stores || []).length;
  const watchStores = groups.A;
  return `
    <section class="hero">
      <p class="eyebrow">Source ${escapeHtml(payload.source || "-")}</p>
      <h1 class="hero-title">今日はどの店を見るべきか</h1>
      <p class="hero-copy">
        利用可能な店舗を上から順に見て、内部指標は必要なときだけ詳細で確認します。
      </p>
      <div class="summary-card">
        <p class="summary-kicker">今日の結論</p>
        <h2 class="summary-title">
          ${escapeHtml(payload.today_conclusion || "")}
        </h2>
        <ul class="summary-lines">
          <li>${
            escapeHtml(
              `${total}店舗中${Number(counts.A || 0) + Number(counts.B || 0)}店舗が利用可能。`,
            )
          }</li>
          <li>${escapeHtml(`注意付き店舗は${counts.B || 0}店舗。`)}</li>
          <li>${escapeHtml(overallActionText(counts, total))}</li>
        </ul>
      </div>
      <div class="watch-panel">
        <h2>今日見る店</h2>
        <p class="watch-copy">まずは A 判定の店舗だけを上から見ます。</p>
        ${
          watchStores.length
            ? `<ul class="watch-list">${watchStores
                .map((store) => `<li>${escapeHtml(store.display_name)}</li>`)
                .join("")}</ul>`
            : `<p class="watch-copy">A 判定の店舗はありません。</p>`
        }
      </div>
      <div class="meta-row">
        <div class="meta-chip">
          <div class="meta-label">データソース</div>
          <div class="meta-value">${escapeHtml(payload.source || "-")}</div>
        </div>
        <div class="meta-chip">
          <div class="meta-label">最終更新日時</div>
          <div class="meta-value">${escapeHtml(payload.generated_at || "-")}</div>
        </div>
        <div class="meta-chip">
          <div class="meta-label">集計対象期間</div>
          <div class="meta-value">${escapeHtml(payload.coverage_window || "-")}</div>
        </div>
        <div class="meta-chip">
          <div class="summary-label">A / B / C</div>
          <div class="meta-value">
            ${escapeHtml(`${counts.A || 0} / ${counts.B || 0} / ${counts.C || 0}`)}
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderTargetsPanel(targets) {
  if (!targets || !targets.summary || !targets.sections) {
    return `
      <section class="target-panel">
        <h2>今日の狙い候補</h2>
        <p class="target-copy">analyze-targets 実行後に候補を表示します。</p>
      </section>
    `;
  }
  const counts = targets.summary.target_counts || {};
  const machineCandidates = targets.sections.machine_candidates || [];
  const raiseCandidates = targets.sections.raise_candidates || [];
  const keepCandidates = targets.sections.keep_candidates || [];
  const patternCandidates = [
    ...(targets.sections.tail_candidates || []),
    ...(targets.sections.cluster_candidates || []),
  ].slice(0, 12);
  return `
    <section class="target-panel">
      <h2>今日の狙い候補</h2>
      <p class="target-copy">
        候補であって断定ではありません。sample_count が少ないものは参考程度として扱います。
      </p>
      <div class="tier-row">
        <div class="tier-chip">
          <div class="tier-label">S候補</div>
          <div class="tier-value">${escapeHtml(counts.S || 0)}</div>
        </div>
        <div class="tier-chip">
          <div class="tier-label">A候補</div>
          <div class="tier-value">${escapeHtml(counts.A || 0)}</div>
        </div>
        <div class="tier-chip">
          <div class="tier-label">B候補</div>
          <div class="tier-value">${escapeHtml(counts.B || 0)}</div>
        </div>
        <div class="tier-chip">
          <div class="tier-label">見送り</div>
          <div class="tier-value">${escapeHtml(counts["見送り"] || 0)}</div>
        </div>
      </div>
      <div class="target-grid">
        ${renderCandidateList(
          "狙い機種",
          "店舗と機種の直近傾向から見る候補です。",
          machineCandidates,
          "候補なし",
        )}
        ${renderCandidateList(
          "上げ狙い台",
          "前日凹みと稼働量から見る候補です。",
          raiseCandidates,
          "候補なし",
        )}
        ${renderCandidateList(
          "据え置き候補",
          "前日プラスと同機種傾向から見る候補です。",
          keepCandidates,
          "候補なし",
        )}
        ${renderCandidateList(
          "末尾・並び候補",
          "sample_count が少ない場合は参考程度です。",
          patternCandidates,
          "候補なし",
        )}
      </div>
    </section>
  `;
}

function cardTemplate(store) {
  const failedUrls = store.failed_machine_urls || [];
  return `
    <article class="store-card" data-grade="${escapeHtml(store.decision_grade)}">
      <div class="store-top">
        <div>
          <h3 class="store-title">${escapeHtml(store.display_name)}</h3>
        </div>
        <div class="badge-row">
          ${renderBadge(`判定 ${store.decision_grade}`, gradeBadgeKind(store.decision_grade))}
          ${renderBadge(store.decision_state, stateBadgeKind(store.decision_grade))}
        </div>
      </div>
      <p class="store-reason">${escapeHtml(store.decision_reason || "")}</p>
      <details class="detail-box">
        <summary>詳細を開く</summary>
        <div class="detail-grid">
          <div class="detail-item">
            <strong>fetch_status</strong>
            <p>${escapeHtml(fetchStatusText(store.fetch_status))}</p>
          </div>
          <div class="detail-item">
            <strong>parse_status</strong>
            <p>${escapeHtml(store.parse_status)}</p>
          </div>
          <div class="detail-item">
            <strong>daily数</strong>
            <p>${escapeHtml(store.daily_count || 0)}</p>
          </div>
          <div class="detail-item">
            <strong>machine数</strong>
            <p>${escapeHtml(store.machine_count || 0)}</p>
          </div>
          <div class="detail-item">
            <strong>unit数</strong>
            <p>${escapeHtml(store.unit_count || 0)}</p>
          </div>
          <div class="detail-item">
            <strong>unit_diff_missing_rate</strong>
            <p>${escapeHtml(store.unit_diff_missing_rate_text)}</p>
          </div>
          <div class="detail-item">
            <strong>failed_machine_pages</strong>
            <p>${escapeHtml(store.failed_machine_pages || 0)}</p>
          </div>
          <div class="detail-item">
            <strong>failed_machine_urls</strong>
            ${failedUrls.length
              ? `<ul class="detail-list">${renderList(failedUrls)}</ul>`
              : `<p>記録なし</p>`}
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

function groupSection(grade, title, copy, stores, compact = false) {
  return `
    <section class="group-panel ${compact ? "compact" : ""}" data-grade="${escapeHtml(grade)}">
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

function mountDashboard(payload, targets) {
  const root = document.getElementById("app");
  const stores = payload.stores || [];

  function render() {
    const groups = groupedStores(stores);

    root.innerHTML = `
      <main class="page">
        ${renderHeroCard(payload, groups)}
        ${renderTargetsPanel(targets)}

        ${groupSection(
          "A",
          "A 通常利用可能",
          "まず最初に見る店舗です。初期表示は判断理由だけに絞っています。",
          groups.A,
        )}
        ${groupSection(
          "B",
          "B 注意付きで利用可能",
          "一部取得失敗はありますが、候補からは外さず次に確認します。",
          groups.B,
        )}
        ${groupSection(
          "C",
          "C 見送り / データ不足",
          "最後に小さく確認する枠です。今日の主候補にはしません。",
          groups.C,
          true,
        )}

        <p class="footer">
          source=${escapeHtml(payload.source || "-")} / raw HTML や SQLite DB は公開していません。
        </p>
      </main>
    `;
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

async function loadTargetsPayload() {
  try {
    const response = await fetch("./data/targets.json", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    return null;
  }
}

Promise.all([loadPayload(), loadTargetsPayload()])
  .then(([payload, targets]) => mountDashboard(payload, targets))
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

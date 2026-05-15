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

function priorityRank(priorityGroup) {
  if (priorityGroup === "main") return 0;
  if (priorityGroup === "sub") return 1;
  return 2;
}

function priorityLabel(priorityGroup) {
  if (priorityGroup === "main") return "main";
  if (priorityGroup === "sub") return "sub";
  return "watch";
}

function priorityDisplayLabel(priorityGroup) {
  if (priorityGroup === "main") return "メイン";
  if (priorityGroup === "sub") return "サブ";
  return "監視";
}

function targetTypeLabel(targetType) {
  if (targetType === "machine_candidate") return "狙い機種";
  if (targetType === "raise_candidate") return "上げ狙い";
  if (targetType === "tail_candidate") return "末尾候補";
  if (targetType === "cluster_candidate") return "並び候補";
  return targetType;
}

function formatSignedNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return "-";
  const prefix = number > 0 ? "+" : "";
  return `${prefix}${number.toLocaleString("ja-JP")}${suffix}`;
}

function formatPlainNumber(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return "-";
  return `${number.toLocaleString("ja-JP")}${suffix}`;
}

function candidatePrimaryLabel(candidate) {
  if (candidate.machine_name && candidate.unit_number) {
    return `${candidate.machine_name} / ${candidate.unit_number}`;
  }
  return candidate.machine_name || candidate.unit_number || "-";
}

function candidateItem(candidate, analysisAnchorDate = "-") {
  const evidence = candidate.evidence || {};
  const reasonText = candidate.reason_text || candidate.reason || "";
  return `
    <li>
      <strong>${escapeHtml(candidate.store_name)}</strong>
      <span class="candidate-meta">
        priority ${escapeHtml(priorityLabel(candidate.priority_group))} /
        ${escapeHtml(candidatePrimaryLabel(candidate))} /
        ${escapeHtml(targetTypeLabel(candidate.target_type))} /
        score ${escapeHtml(candidate.score)} /
        confidence ${escapeHtml(candidate.confidence)}
      </span>
      <span class="candidate-meta">${escapeHtml(reasonText)}</span>
      <span class="candidate-meta">
        根拠:
        prev_diff=${escapeHtml(evidence.previous_day_diff ?? "-")} /
        prev_games=${escapeHtml(evidence.previous_day_games ?? "-")} /
        sample=${escapeHtml(evidence.sample_count ?? "-")} /
        anchor=${escapeHtml(analysisAnchorDate)}
      </span>
      ${
        candidate.caution
          ? `<span class="candidate-meta">注意: ${escapeHtml(candidate.caution)}</span>`
          : ""
      }
    </li>
  `;
}

function renderCandidateList(title, copy, candidates, emptyLabel, analysisAnchorDate = "-") {
  return `
    <div class="target-card">
      <h3>${escapeHtml(title)}</h3>
      <p class="target-copy">${escapeHtml(copy)}</p>
      ${
        candidates && candidates.length
          ? `<ul class="candidate-list">${candidates
              .map((candidate) => candidateItem(candidate, analysisAnchorDate))
              .join("")}</ul>`
          : `<p class="target-copy">${escapeHtml(emptyLabel)}</p>`
      }
    </div>
  `;
}

function sortedCandidatesByPriority(candidates) {
  return [...(candidates || [])].sort((left, right) => {
    const leftRank = priorityRank(left.priority_group);
    const rightRank = priorityRank(right.priority_group);
    if (leftRank !== rightRank) return leftRank - rightRank;
    return Number(right.score || 0) - Number(left.score || 0);
  });
}

function renderPriorityStoreList(title, className, stores) {
  return `
    <div class="priority-card ${escapeHtml(className)}">
      <h3>${escapeHtml(title)}</h3>
      ${
        stores && stores.length
          ? `<ul class="candidate-list">${stores
              .map((store) => `<li><strong>${escapeHtml(store)}</strong></li>`)
              .join("")}</ul>`
          : `<p class="target-copy">該当店舗なし</p>`
      }
    </div>
  `;
}

function renderFocusCard(candidate, analysisAnchorDate, storeMeta = {}) {
  const label = candidatePrimaryLabel(candidate);
  const evidence = candidate.evidence || {};
  const reasonText = candidate.reason_text || candidate.reason || "";
  const priorityGrade =
    candidate.priority_group === "main"
      ? "A"
      : candidate.priority_group === "sub"
        ? "B"
        : "C";
  const confidenceGrade =
    candidate.confidence === "A" ? "A" : candidate.confidence === "B" ? "B" : "C";
  const negativeStreakDays = evidence.negative_streak_days;
  const diffText = formatSignedNumber(evidence.previous_day_diff, "枚");
  const gamesText = formatPlainNumber(evidence.previous_day_games, "G");
  const avgDiffText = formatSignedNumber(evidence.recent_avg_diff, "枚");
  const avgGamesText = formatPlainNumber(evidence.recent_avg_games, "G");
  const missingRateText = storeMeta.unit_diff_missing_rate_text || "-";
  const failedMachinePages = storeMeta.failed_machine_pages || 0;
  const sampleCount = evidence.sample_count ?? "-";
  return `
    <article class="focus-card ${escapeHtml(priorityLabel(candidate.priority_group))}">
      <div class="badge-row">
        ${renderBadge(
          priorityDisplayLabel(candidate.priority_group),
          stateBadgeKind(priorityGrade),
        )}
        ${renderBadge(targetTypeLabel(candidate.target_type), gradeBadgeKind(confidenceGrade))}
        ${renderBadge(`信頼度 ${candidate.confidence}`, gradeBadgeKind(confidenceGrade))}
      </div>
      <h3 class="focus-title">${escapeHtml(candidate.store_name)}</h3>
      <p class="focus-kicker">${escapeHtml(label)}</p>
      <p class="focus-detail">
        ${escapeHtml(targetTypeLabel(candidate.target_type))}
      </p>
      <p class="focus-detail">
        前回
        <span class="${
          diffText.startsWith("-") ? "metric-negative" : "metric-strong"
        }">${escapeHtml(diffText)}</span>
        /
        <span class="metric-strong">${escapeHtml(gamesText)}</span>
      </p>
      <p class="focus-detail">
        ${
          negativeStreakDays
            ? `${escapeHtml(formatPlainNumber(negativeStreakDays, "日"))}連続凹み`
            : "連続凹み情報なし"
        }
      </p>
      <p class="focus-detail">
        同機種平均 ${escapeHtml(avgDiffText)} / ${escapeHtml(avgGamesText)}
      </p>
      <p class="target-copy">${escapeHtml(reasonText)}</p>
      <p class="focus-kicker">データ基準日: ${escapeHtml(analysisAnchorDate || "-")}</p>
      <details class="focus-details">
        <summary>詳細を開く</summary>
        <div class="focus-details-grid">
          <div class="detail-item">
            <strong>score</strong>
            <p class="focus-scoreline">
              raw ${escapeHtml(candidate.score)} /
              adjusted ${escapeHtml(candidate.adjusted_score ?? candidate.score)}
            </p>
          </div>
          <div class="detail-item">
            <strong>sample_count</strong>
            <p>${escapeHtml(String(sampleCount))}</p>
          </div>
          <div class="detail-item">
            <strong>unit_diff_missing_rate</strong>
            <p>${escapeHtml(missingRateText)}</p>
          </div>
          <div class="detail-item">
            <strong>failed_machine_pages</strong>
            <p>${escapeHtml(String(failedMachinePages))}</p>
          </div>
          <div class="detail-item">
            <strong>machine平均</strong>
            <p>${escapeHtml(avgDiffText)} / ${escapeHtml(avgGamesText)}</p>
          </div>
          ${
            candidate.caution
              ? `<div class="detail-item">
                  <strong>注意</strong>
                  <p>${escapeHtml(candidate.caution)}</p>
                </div>`
              : ""
          }
        </div>
      </details>
    </article>
  `;
}

function renderMainStoreSection(section, analysisAnchorDate, copy, storeMeta = {}) {
  const raiseCandidates = section.raise_candidates || [];
  const clusterCandidates = section.cluster_candidates || [];
  const machineCandidates = section.machine_candidates || [];
  const tailCandidates = section.tail_candidates || [];
  return `
    <div class="target-card">
      <h3>${escapeHtml(section.store_name || section.store_id || "-")}</h3>
      <p class="target-copy">${escapeHtml(copy)}</p>
      <h4 class="target-section-title">上げ狙い台</h4>
      ${
        raiseCandidates.length
          ? `<div class="focus-grid">${raiseCandidates
              .map((candidate) => renderFocusCard(candidate, analysisAnchorDate, storeMeta))
              .join("")}</div>`
          : `<p class="target-copy">候補なし</p>`
      }
      <h4 class="target-section-title">並び候補</h4>
      ${
        clusterCandidates.length
          ? `<div class="focus-grid">${clusterCandidates
              .map((candidate) => renderFocusCard(candidate, analysisAnchorDate, storeMeta))
              .join("")}</div>`
          : `<p class="target-copy">候補なし</p>`
      }
      <h4 class="target-section-title">狙い機種</h4>
      ${
        machineCandidates.length
          ? `<div class="focus-grid">${machineCandidates
              .map((candidate) => renderFocusCard(candidate, analysisAnchorDate, storeMeta))
              .join("")}</div>`
          : `<p class="target-copy">候補なし</p>`
      }
      <h4 class="target-section-title">末尾候補</h4>
      ${
        tailCandidates.length
          ? `<div class="focus-grid">${tailCandidates
              .map((candidate) => renderFocusCard(candidate, analysisAnchorDate, storeMeta))
              .join("")}</div>`
          : `<p class="target-copy">候補なし</p>`
      }
    </div>
  `;
}

function renderHeroCard(payload, targets) {
  const targetStoreCount = payload.target_store_count || (payload.stores || []).length;
  const mainStores = (targets && targets.priority_groups && targets.priority_groups.main) || [];
  const subStores = (targets && targets.priority_groups && targets.priority_groups.sub) || [];
  const anchorDate = (targets && targets.analysis_anchor_date) || payload.target_date || "-";
  const anchorNotice = (targets && targets.analysis_anchor_notice) || "";
  return `
    <section class="hero">
      <p class="eyebrow">slorepo / 対象${escapeHtml(String(targetStoreCount))}店舗</p>
      <h1 class="hero-title">今日の狙い</h1>
      <p class="hero-copy">データ基準日: ${escapeHtml(anchorDate)}</p>
      ${anchorNotice ? `<p class="hero-copy">${escapeHtml(anchorNotice)}</p>` : ""}
      <div class="summary-card">
        <p class="summary-kicker">今日の結論</p>
        <h2 class="summary-title">
          今日はメイン2店舗を優先。
        </h2>
        <ul class="summary-lines">
          <li>${escapeHtml(`まずは${mainStores.join("、")}を確認。`)}</li>
          <li>${escapeHtml(`サブは${subStores.join("、")}。`)}</li>
          <li>${escapeHtml(payload.today_conclusion || "")}</li>
        </ul>
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
  const highlightCounts = targets.summary.highlight_counts || {};
  const priorityGroups = targets.priority_groups || {};
  const anchorNotice = targets.analysis_anchor_notice || "";
  const analysisAnchorDate = targets.analysis_anchor_date || "-";
  const highlights = targets.highlights || {};
  const mainStoreSections = targets.main_store_sections || {};
  const subStoreSections = targets.sub_store_sections || {};
  const storeMetaMap = Object.fromEntries(
    (targets.store_scores || []).map((row) => [row.store_id, row]),
  );
  const topCandidates = highlights.top_candidates || [];
  const machineCandidates = sortedCandidatesByPriority(targets.sections.machine_candidates || []);
  const raiseCandidates = sortedCandidatesByPriority(targets.sections.raise_candidates || []);
  const patternCandidates = sortedCandidatesByPriority([
    ...(targets.sections.tail_candidates || []),
    ...(targets.sections.cluster_candidates || []),
  ]);
  return `
    <section class="target-panel">
      <h2>今日の最優先候補</h2>
      <p class="target-copy">まずこの5件を見ます。scoreより理由を優先して並べています。</p>
      ${
        topCandidates.length
          ? `<div class="focus-grid">${topCandidates
              .map((candidate) =>
                renderFocusCard(
                  candidate,
                  analysisAnchorDate,
                  storeMetaMap[candidate.store_id] || {},
                ),
              )
              .join("")}</div>`
          : `<p class="target-copy">最優先候補はありません。</p>`
      }
      <div class="priority-overview">
        ${renderPriorityStoreList("今日見るべき店", "main", priorityGroups.main || [])}
        ${renderPriorityStoreList("サブ候補", "sub", priorityGroups.sub || [])}
      </div>
      <h3 class="section-title">メイン店</h3>
      <p class="section-copy">コスモジャパン大府とマルシン777を深く見ます。</p>
      <div class="target-grid">
        ${renderMainStoreSection(
          mainStoreSections.cosmo_obu || { store_id: "cosmo_obu" },
          analysisAnchorDate,
          "メイン店を深く見るための curated list です。最大10件、tail は最大2件までです。",
          storeMetaMap.cosmo_obu || {},
        )}
        ${renderMainStoreSection(
          mainStoreSections.marushin_777 || { store_id: "marushin_777" },
          analysisAnchorDate,
          "メイン店を深く見るための curated list です。最大10件、tail は最大2件までです。",
          storeMetaMap.marushin_777 || {},
        )}
      </div>
      <h3 class="section-title">サブ店</h3>
      <p class="section-copy">APANCLUB弘法通りとKEIZギャラリエアピタを次に見ます。</p>
      <div class="target-grid">
        ${renderMainStoreSection(
          subStoreSections.apan_kobo || { store_id: "apan_kobo" },
          analysisAnchorDate,
          "サブ店の curated list です。最大5件まで表示します。",
          storeMetaMap.apan_kobo || {},
        )}
        ${renderMainStoreSection(
          subStoreSections.keiz_galerie_apita || { store_id: "keiz_galerie_apita" },
          analysisAnchorDate,
          "サブ店の curated list です。最大5件まで表示します。",
          storeMetaMap.keiz_galerie_apita || {},
        )}
      </div>
      <details class="note-card">
        <summary>詳細と注意点を開く</summary>
        <p class="target-copy">候補の一覧と内部指標です。初見ではここまで見なくて構いません。</p>
        ${anchorNotice ? `<p class="target-copy">注意: ${escapeHtml(anchorNotice)}</p>` : ""}
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
            "main → sub の4店舗だけを並べています。",
            machineCandidates,
            "候補なし",
            analysisAnchorDate,
          )}
          ${renderCandidateList(
            "上げ狙い台",
            "main 店舗を最優先に確認し、次に sub 店舗を見ます。",
            raiseCandidates,
            "候補なし",
            analysisAnchorDate,
          )}
          ${renderCandidateList(
            "末尾・並び候補",
            "sample_count が少ない場合は参考程度です。",
            patternCandidates,
            "候補なし",
            analysisAnchorDate,
          )}
        </div>
      </details>
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
  const notes = payload.notes || [];

  function render() {
    root.innerHTML = `
      <main class="page">
        ${renderHeroCard(payload, targets)}
        ${renderTargetsPanel(targets)}
        <section class="note-card">
          <h2>注意点</h2>
          <ul class="candidate-list">${renderList(notes, "追加注意なし")}</ul>
        </section>
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

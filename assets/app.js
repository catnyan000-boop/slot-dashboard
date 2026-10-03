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

function coverageBadgeKind(state) {
  if (state === "normal") return "A";
  if (state === "caution") return "B";
  return "C";
}

function formatCoverageRate(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (Number.isNaN(number)) return "-";
  return `${(number * 100).toFixed(1)}%`;
}

function renderCoverageCard(row) {
  return `
    <article class="coverage-card ${escapeHtml(row.coverage_state || "caution")}">
      <div class="coverage-top">
        <div>
          <h3 class="coverage-title">${escapeHtml(row.store_name || row.store_id || "-")}</h3>
          <p class="coverage-days">
            ${escapeHtml(String(row.available_days ?? 0))}/
            ${escapeHtml(String(row.requested_days ?? 0))}日
          </p>
        </div>
        <div class="badge-row">
          ${renderBadge(
            row.coverage_state_label || "注意",
            coverageBadgeKind(row.coverage_state),
          )}
          ${renderBadge(
            `failed ${row.failed_machine_pages || 0}`,
            gradeBadgeKind((row.failed_machine_pages || 0) > 0 ? "B" : "A"),
          )}
        </div>
      </div>
      <p class="coverage-meta">
        取得範囲 ${escapeHtml(row.oldest_date || "-")} 〜 ${escapeHtml(row.latest_date || "-")}
      </p>
      <p class="coverage-meta">
        coverage_rate ${escapeHtml(formatCoverageRate(row.coverage_rate))} /
        daily ${escapeHtml(String(row.daily_count ?? 0))} /
        machine ${escapeHtml(String(row.machine_count ?? 0))} /
        unit ${escapeHtml(String(row.unit_count ?? 0))}
      </p>
    </article>
  `;
}

function renderCoveragePanel(targets) {
  const rows = (targets && targets.store_coverage) || [];
  if (!rows.length) return "";
  return `
    <div class="coverage-panel">
      <h3 class="section-title">データ充足状況</h3>
      <p class="section-copy">
        requested_days
        ${escapeHtml(String(targets.requested_days || targets.lookback_days || "-"))}
        日指定に対して、85日以上は通常、80〜84日は注意、80日未満は不足として見ます。
      </p>
      <div class="coverage-grid">
        ${rows.map((row) => renderCoverageCard(row)).join("")}
      </div>
    </div>
  `;
}

function renderTrendList(title, rows, renderRow, emptyLabel = "候補なし") {
  return `
    <div>
      <h4 class="trend-subtitle">${escapeHtml(title)}</h4>
      ${
        rows && rows.length
          ? `<ul class="trend-list">${rows.map((row) => renderRow(row)).join("")}</ul>`
          : `<p class="trend-caption">${escapeHtml(emptyLabel)}</p>`
      }
    </div>
  `;
}

function renderTrendMachineRow(row) {
  return `
    <li>
      <strong>${escapeHtml(row.machine_name)}</strong>
      <div class="trend-caption">
        90日 ${escapeHtml(formatSignedNumber(row.avg_diff_90, "枚"))} /
        ${escapeHtml(formatPlainNumber(row.avg_game_90, "G"))}、
        30日 ${escapeHtml(formatSignedNumber(row.avg_diff_30, "枚"))} /
        ${escapeHtml(formatPlainNumber(row.avg_game_30, "G"))}
      </div>
      <div class="trend-caption">
        サンプル ${escapeHtml(formatPlainNumber(row.sample_days, "日"))} /
        trend ${escapeHtml(String(row.trend_score ?? row.machine_trend_score ?? "-"))}
      </div>
      <div class="trend-caption">${escapeHtml(row.reason || "")}</div>
    </li>
  `;
}

function renderTrendRangeRow(row) {
  return `
    <li>
      <strong>${escapeHtml(row.unit_range)}</strong>
      <div class="trend-caption">
        平均 ${escapeHtml(formatSignedNumber(row.avg_diff, "枚"))} /
        ${escapeHtml(formatPlainNumber(row.avg_game, "G"))}、
        プラス率 ${escapeHtml(formatCoverageRate(row.plus_rate))}
      </div>
      <div class="trend-caption">
        対象台数 ${escapeHtml(formatPlainNumber(row.unit_count, "台"))} /
        サンプル ${escapeHtml(formatPlainNumber(row.sample_count, "件"))} /
        trend ${escapeHtml(String(row.trend_score ?? row.unit_range_score ?? "-"))}
      </div>
      <div class="trend-caption">${escapeHtml(row.reason || "")}</div>
    </li>
  `;
}

function renderTrendTailRow(row) {
  return `
    <li>
      <strong>末尾${escapeHtml(row.tail)}</strong>
      <div class="trend-caption">
        平均 ${escapeHtml(formatSignedNumber(row.avg_diff, "枚"))} /
        ${escapeHtml(formatPlainNumber(row.avg_game, "G"))}、
        プラス率 ${escapeHtml(formatCoverageRate(row.plus_rate))}
      </div>
      <div class="trend-caption">
        サンプル ${escapeHtml(formatPlainNumber(row.sample_count, "件"))} /
        trend ${escapeHtml(String(row.trend_score ?? row.tail_trend_score ?? "-"))}
      </div>
      <div class="trend-caption">${escapeHtml(row.reason || "")}</div>
    </li>
  `;
}

function renderTrendRaiseRow(row) {
  const reasonText = row.reason_text || row.reason || "";
  return `
    <li>
      <strong>${escapeHtml(candidatePrimaryLabel(row))}</strong>
      <div class="trend-caption">
        前回 ${escapeHtml(formatSignedNumber(row.previous_day_diff, "枚"))} /
        ${escapeHtml(formatPlainNumber(row.previous_day_games, "G"))}、
        ${escapeHtml(formatPlainNumber(row.negative_streak_days, "日"))}連続凹み
      </div>
      <div class="trend-caption">
        同機種平均 ${escapeHtml(formatSignedNumber(row.same_machine_avg_diff, "枚"))} /
        ${escapeHtml(formatPlainNumber(row.same_machine_avg_games, "G"))}
      </div>
      <div class="trend-caption">
        ${escapeHtml(row.machine_trend_overlap_text || "")}
        ${row.range_trend_overlap_text ? ` / ${escapeHtml(row.range_trend_overlap_text)}` : ""}
        ${row.tail_trend_overlap_text ? ` / ${escapeHtml(row.tail_trend_overlap_text)}` : ""}
      </div>
      <div class="trend-caption">${escapeHtml(reasonText)}</div>
    </li>
  `;
}

function renderTrendMachineFront(row) {
  return `
    <div class="trend-front">
      <div class="trend-front-name">${escapeHtml(row.machine_name)}</div>
      <p class="trend-front-metric">
        90日 ${escapeHtml(formatSignedNumber(row.avg_diff_90, "枚"))} ／
        30日 ${escapeHtml(formatSignedNumber(row.avg_diff_30, "枚"))} ・
        ${escapeHtml(formatPlainNumber(row.sample_days, "日"))}
      </p>
      ${
        Number(row.raise_overlap_count) > 0
          ? `<span class="trend-tag">凹み重なり${escapeHtml(
              formatPlainNumber(row.raise_overlap_count),
            )}</span>`
          : ""
      }
      <p class="trend-front-reason">${escapeHtml(row.reason || "")}</p>
    </div>
  `;
}

function renderTrendRangeFront(row, showReason) {
  return `
    <div class="trend-front">
      <div class="trend-front-name">${escapeHtml(row.unit_range)}</div>
      <p class="trend-front-metric">
        平均 ${escapeHtml(formatSignedNumber(row.avg_diff, "枚"))} ・
        プラス率 ${escapeHtml(formatCoverageRate(row.plus_rate))}
      </p>
      ${
        showReason && row.reason
          ? `<p class="trend-front-reason">${escapeHtml(row.reason)}</p>`
          : ""
      }
    </div>
  `;
}

function renderTrendTailFront(row) {
  return `
    <div class="trend-front">
      <div class="trend-front-name">末尾${escapeHtml(row.tail)}</div>
      <p class="trend-front-metric">
        平均 ${escapeHtml(formatSignedNumber(row.avg_diff, "枚"))} ・
        プラス率 ${escapeHtml(formatCoverageRate(row.plus_rate))}
      </p>
      <p class="trend-front-reason">${escapeHtml(row.reason || "")}</p>
    </div>
  `;
}

function renderTrendRaiseFront(row) {
  const reasonText = row.reason_text || row.reason || "";
  return `
    <div class="trend-front">
      <div class="trend-front-name">${escapeHtml(candidatePrimaryLabel(row))}</div>
      <p class="trend-front-metric">
        前回 ${escapeHtml(formatSignedNumber(row.previous_day_diff, "枚"))} ・
        ${escapeHtml(formatPlainNumber(row.negative_streak_days, "日"))}連続凹み
      </p>
      <p class="trend-front-reason">${escapeHtml(reasonText)}</p>
    </div>
  `;
}

function renderTrendStoreCard(store) {
  const machineRows = store.top_machines || [];
  const workloadMachineRows = store.workload_machines || [];
  const referenceMachineRows = store.reference_machines || [];
  const rangeRows = store.top_unit_ranges || [];
  const referenceRangeRows = store.reference_unit_ranges || [];
  const tailRows = store.top_tails || [];
  const referenceTailRows = store.reference_tails || [];
  const raiseRows = store.top_raise_units || [];
  const raiseFrontRows = raiseRows.slice(0, 2);
  const raiseRestRows = raiseRows.slice(2);
  const cautionRows = store.cautions || [];
  const priorityKind = stateBadgeKind(store.priority_group === "main" ? "A" : "B");
  const coverageKind = gradeBadgeKind(
    (store.available_days || 0) >= 85
      ? "A"
      : (store.available_days || 0) >= 80
        ? "B"
        : "C",
  );
  const hasReference =
    workloadMachineRows.length ||
    referenceMachineRows.length ||
    referenceRangeRows.length ||
    referenceTailRows.length ||
    raiseRestRows.length ||
    (store.trend_summary || "").length ||
    cautionRows.length;
  return `
    <article class="trend-store-card">
      <div class="badge-row">
        ${renderBadge(priorityDisplayLabel(store.priority_group), priorityKind)}
        ${renderBadge(
          `${store.available_days || 0}/${store.requested_days || 0}日`,
          coverageKind,
        )}
      </div>
      <h3 class="trend-title">${escapeHtml(store.store_name || store.store_id || "-")}</h3>
      <h4 class="trend-subtitle">本命機種</h4>
      ${
        machineRows.length
          ? machineRows.map((row) => renderTrendMachineFront(row)).join("")
          : `<p class="trend-empty">本命機種なし。この店は台番帯・上げ狙い候補を中心に確認。</p>`
      }
      ${
        rangeRows.length
          ? `<h4 class="trend-subtitle">注目台番帯</h4>${rangeRows
              .map((row, i) => renderTrendRangeFront(row, i === 0))
              .join("")}`
          : ""
      }
      ${
        tailRows.length
          ? `<h4 class="trend-subtitle">注目末尾</h4>${tailRows
              .map((row) => renderTrendTailFront(row))
              .join("")}`
          : ""
      }
      ${
        raiseFrontRows.length
          ? `<h4 class="trend-subtitle">上げ狙い候補</h4>${raiseFrontRows
              .map((row) => renderTrendRaiseFront(row))
              .join("")}`
          : ""
      }
      ${
        hasReference
          ? `<details class="focus-details">
              <summary>参考・稼働注目を開く</summary>
              ${renderTrendList(
                "稼働注目機種",
                workloadMachineRows,
                renderTrendMachineRow,
                "該当なし",
              )}
              ${renderTrendList(
                "参考機種",
                referenceMachineRows,
                renderTrendMachineRow,
                "該当なし",
              )}
              ${renderTrendList(
                "参考台番帯",
                referenceRangeRows,
                renderTrendRangeRow,
                "該当なし",
              )}
              ${renderTrendList(
                "参考末尾",
                referenceTailRows,
                renderTrendTailRow,
                "該当なし",
              )}
              ${
                raiseRestRows.length
                  ? renderTrendList(
                      "上げ狙い候補（続き）",
                      raiseRestRows,
                      renderTrendRaiseRow,
                      "該当なし",
                    )
                  : ""
              }
              ${
                store.trend_summary
                  ? `<h4 class="trend-subtitle">総括</h4>
                     <p class="trend-summary">${escapeHtml(store.trend_summary)}</p>`
                  : ""
              }
              ${
                cautionRows.length
                  ? `<h4 class="trend-subtitle">注意点</h4>
                     <ul class="trend-list">${cautionRows
                       .map((row) => `<li>${escapeHtml(row)}</li>`)
                       .join("")}</ul>`
                  : ""
              }
            </details>`
          : ""
      }
    </article>
  `;
}

function renderTomorrowRibbon(trends) {
  if (!trends || !trends.stores || !trends.stores.length) {
    return "";
  }
  const rows = (trends.stores || [])
    .map((store) => {
      const topMachine = (store.top_machines || [])[0];
      const topRange = (store.top_unit_ranges || [])[0];
      const machineText = topMachine
        ? `本命 ${escapeHtml(topMachine.machine_name)}`
        : "本命なし、台番帯中心";
      const rangeText = topRange
        ? ` ／ 注目帯 ${escapeHtml(topRange.unit_range)}`
        : "";
      return `
        <div class="ribbon-row">
          <div class="ribbon-head">
            <span class="ribbon-store">${escapeHtml(
              store.store_name || store.store_id || "-",
            )}</span>
            ${renderBadge(
              priorityDisplayLabel(store.priority_group),
              stateBadgeKind(store.priority_group === "main" ? "A" : "B"),
            )}
          </div>
          <div class="ribbon-line">${machineText}${rangeText}</div>
        </div>
      `;
    })
    .join("");
  return `
    <section class="trend-panel target-panel">
      <h2>明日ここを見る</h2>
      <p class="target-copy">次営業日に優先確認する順です。score は出していません。</p>
      <div class="tomorrow-ribbon">${rows}</div>
    </section>
  `;
}

function renderTrendsPanel(trends) {
  if (!trends || !trends.stores) {
    return `
      <section class="trend-panel target-panel">
        <h2>明日の傾向予測</h2>
        <p class="target-copy">analyze-trends 実行後に傾向を表示します。</p>
      </section>
    `;
  }
  return `
    <section class="trend-panel target-panel">
      <h2>明日の傾向予測</h2>
      <p class="target-copy">
        直近 ${escapeHtml(String(trends.requested_days || "-"))} 日の傾向を集計しています。
        データ基準日は ${escapeHtml(trends.analysis_anchor_date || "-")} です。
      </p>
      ${
        trends.analysis_anchor_notice
          ? `<p class="target-copy">${escapeHtml(trends.analysis_anchor_notice)}</p>`
          : ""
      }
      <div class="trend-grid">
        ${(trends.stores || []).map((store) => renderTrendStoreCard(store)).join("")}
      </div>
    </section>
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
      <h1 class="hero-title">次営業日の狙い</h1>
      <p class="hero-copy">データ基準日: ${escapeHtml(anchorDate)}</p>
      ${anchorNotice ? `<p class="hero-copy">${escapeHtml(anchorNotice)}</p>` : ""}
      <div class="summary-card">
        <p class="summary-kicker">明日ここを見る</p>
        <h2 class="summary-title">
          次営業日はメイン2店舗を優先確認。
        </h2>
        <ul class="summary-lines">
          <li>${escapeHtml(`まず${mainStores.join("、")}を確認。`)}</li>
          <li>${escapeHtml(`サブは${subStores.join("、")}。`)}</li>
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
      ${renderCoveragePanel(targets)}
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

function renderRecentMinrepoPanel(recent) {
  if (!recent || !recent.has_recent || !recent.stores) {
    return "";
  }
  const cards = (recent.stores || [])
    .filter((store) => (store.recent_days || []).length)
    .map((store) => {
      const days = (store.recent_days || [])
        .map((day) => {
          const machines = (day.top_machines || [])
            .map(
              (m) => `
                <li>
                  <strong>${escapeHtml(m.machine_name)}</strong>
                  <span class="recent-machine-meta">
                    平均 ${escapeHtml(formatSignedNumber(m.avg_diff, "枚"))} ・
                    ${escapeHtml(formatPlainNumber(m.unit_count, "台"))}
                  </span>
                </li>`,
            )
            .join("");
          return `
            <div class="recent-day">
              <div class="recent-day-head">${escapeHtml(day.report_date)}</div>
              <p class="recent-day-metric">
                店平均 ${escapeHtml(formatSignedNumber(day.avg_diff, "枚"))} ・
                総差枚 ${escapeHtml(formatSignedNumber(day.total_diff, "枚"))} ・
                平均 ${escapeHtml(formatPlainNumber(day.avg_game, "G"))} ・
                勝率 ${escapeHtml(formatCoverageRate(day.win_rate))} ・
                ${escapeHtml(formatPlainNumber(day.total_units, "台"))}
              </p>
              ${
                machines
                  ? `<ul class="recent-machine-list">${machines}</ul>`
                  : `<p class="recent-day-metric">機種内訳なし</p>`
              }
            </div>
          `;
        })
        .join("");
      return `
        <article class="recent-store-card">
          <div class="badge-row">
            ${renderBadge(
              priorityDisplayLabel(store.priority_group),
              stateBadgeKind(store.priority_group === "main" ? "A" : "B"),
            )}
            ${renderBadge(
              `slorepo最新 ${store.base_latest_date || "-"}`,
              "neutral",
            )}
          </div>
          <h3 class="recent-title">${escapeHtml(store.store_name || store.store_id || "-")}</h3>
          ${days}
        </article>
      `;
    })
    .join("");
  if (!cards) {
    return "";
  }
  return `
    <section class="trend-panel target-panel">
      <h2>直近実績（みんレポ・参考）</h2>
      <p class="target-copy">${escapeHtml(recent.note || "")}</p>
      <p class="target-copy">
        slorepo が未公開の直近日だけを生実績で表示しています。
        本命・狙いの90日分析には未反映です。
      </p>
      <div class="recent-grid">${cards}</div>
    </section>
  `;
}

function patternHeatClass(avg) {
  if (avg === null || avg === undefined) return "heat-na";
  if (avg >= 2000) return "heat-5";
  if (avg >= 800) return "heat-4";
  if (avg >= -200) return "heat-3";
  if (avg >= -1200) return "heat-2";
  return "heat-1";
}

function targetWeekdayChar(dateStr) {
  if (!dateStr) return null;
  const map = ["日", "月", "火", "水", "木", "金", "土"];
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return map[d.getDay()];
}

function aimChip(label, avg, opts) {
  const o = opts || {};
  const hasAvg = avg !== null && avg !== undefined && avg !== "";
  const cls = patternHeatClass(hasAvg ? Number(avg) : null);
  const valueText = hasAvg
    ? formatSignedNumber(Math.round(Number(avg)), "枚")
    : "-";
  const meta = [];
  if (o.plus_rate !== undefined && o.plus_rate !== null) {
    meta.push(
      `P${(Math.max(0, Math.min(1, Number(o.plus_rate))) * 100).toFixed(0)}%`,
    );
  }
  if (o.n !== undefined && o.n !== null) {
    meta.push(`n${formatPlainNumber(o.n)}`);
  }
  if (o.note) {
    meta.push(escapeHtml(o.note));
  }
  return (
    `<div class="aim-chip ${cls}">` +
    `<span class="aim-chip-label">${escapeHtml(label)}</span>` +
    `<span class="aim-chip-value">${escapeHtml(valueText)}</span>` +
    (meta.length
      ? `<span class="aim-chip-meta">${escapeHtml(meta.join(" / "))}</span>`
      : "") +
    `</div>`
  );
}

function renderDailyTargetsPanel(patterns, targets) {
  const targetDate =
    (patterns && patterns.target_date) ||
    (targets && targets.target_date) ||
    "";
  const wd = targetWeekdayChar(targetDate);
  const stores = ((patterns && patterns.stores) || []).filter(
    (s) => (s.days || 0) > 0,
  );
  if (!stores.length || !wd) {
    return `
      <section class="aim-panel">
        <h2>🎯 本日の狙い目</h2>
        <p class="target-copy">傾向データ（patterns.json）の生成後に表示します。</p>
      </section>
    `;
  }
  const ordered = [...stores].sort(
    (a, b) => priorityRank(a.priority_group) - priorityRank(b.priority_group),
  );
  const tailCands =
    (targets && targets.sections && targets.sections.tail_candidates) || [];
  const clusterCands =
    (targets && targets.sections && targets.sections.cluster_candidates) || [];
  const cards = ordered
    .map((store) => {
      const bands = (store.weekday_bands && store.weekday_bands[wd]) || [];
      const tails = (store.weekday_tails && store.weekday_tails[wd]) || [];
      const myClusters = clusterCands.filter(
        (c) => c.store_id === store.store_id,
      );
      const myTailCands = tailCands.filter(
        (c) => c.store_id === store.store_id,
      );
      const bandChips = bands
        .slice(0, 4)
        .map((b) =>
          aimChip(`${b.band}番台`, b.avg_diff, {
            plus_rate: b.plus_rate,
            n: b.n,
          }),
        )
        .join("");
      const clusterChips = myClusters
        .slice(0, 3)
        .map((c) => {
          const ev = c.evidence || {};
          return aimChip(
            `${c.machine_name || ""} ${c.unit_number || ""}`.trim(),
            ev.previous_day_diff,
            { note: "並び", n: ev.sample_count },
          );
        })
        .join("");
      const tailChips = tails
        .slice(0, 5)
        .map((t) => aimChip(`末尾${t.tail}`, t.avg_diff, {}))
        .join("");
      const tailCandChips = myTailCands
        .map((c) => {
          const ev = c.evidence || {};
          return aimChip(c.unit_number || "末尾?", ev.recent_avg_diff, {
            note: "直近強",
            n: ev.sample_count,
          });
        })
        .join("");
      return `
        <article class="aim-store-card aim-${escapeHtml(
          store.priority_group === "main" ? "main" : "sub",
        )}">
          <div class="aim-store-head">
            <h3>${escapeHtml(store.store_name || store.store_id || "-")}</h3>
            <span class="aim-wd">${escapeHtml(wd)}曜</span>
            ${renderBadge(
              priorityDisplayLabel(store.priority_group),
              stateBadgeKind(store.priority_group === "main" ? "A" : "B"),
            )}
          </div>
          <h4 class="aim-sub">台番帯（この曜日に強い順）</h4>
          <div class="aim-chips">${
            bandChips + clusterChips ||
            '<span class="trend-caption">該当なし</span>'
          }</div>
          <h4 class="aim-sub">末尾（この曜日に強い順）</h4>
          <div class="aim-chips">${
            tailChips + tailCandChips ||
            '<span class="trend-caption">該当なし</span>'
          }</div>
        </article>
      `;
    })
    .join("");
  return `
    <section class="aim-panel">
      <h2>🎯 本日の狙い目（${escapeHtml(targetDate)} ${escapeHtml(
        wd,
      )}曜）</h2>
      <p class="target-copy">
        当日分の狙い目です（データは最新取得日が基準＝slorepo公開遅延あり）。
        過去${escapeHtml(
          String((patterns && patterns.requested_days) || "-"),
        )}日の曜日傾向＋直近の狙い候補を統合。色が濃い＝強い、Pはプラス率。
      </p>
      <div class="aim-grid">${cards}</div>
    </section>
  `;
}

function renderRaisePanel(targets) {
  const raise =
    (targets && targets.sections && targets.sections.raise_candidates) || [];
  if (!raise.length) {
    return `
      <section class="aim-panel raise-panel">
        <h2>🔼 上げ狙い</h2>
        <p class="target-copy">凹み上げ候補はありません。</p>
      </section>
    `;
  }
  const sorted = sortedCandidatesByPriority(raise);
  const rows = sorted
    .map((c) => {
      const ev = c.evidence || {};
      const streak =
        ev.negative_streak_days !== null &&
        ev.negative_streak_days !== undefined
          ? `${formatPlainNumber(ev.negative_streak_days)}日連続凹み`
          : "";
      return `
        <article class="raise-card aim-${escapeHtml(
          c.priority_group === "main" ? "main" : "sub",
        )}">
          <div class="raise-head">
            <strong>${escapeHtml(c.store_name || "-")}</strong>
            ${renderBadge(c.confidence || "-", stateBadgeKind(c.confidence))}
          </div>
          <div class="raise-name">${escapeHtml(
            c.machine_name || "-",
          )} ${escapeHtml(c.unit_number || "")}</div>
          <div class="raise-meta">${
            ev.previous_day_diff !== null && ev.previous_day_diff !== undefined
              ? `前回 ${escapeHtml(formatSignedNumber(ev.previous_day_diff, "枚"))}`
              : ""
          }${streak ? ` ／ ${escapeHtml(streak)}` : ""}</div>
          <div class="raise-reason">${escapeHtml(
            c.reason || c.reason_text || "",
          )}</div>
        </article>
      `;
    })
    .join("");
  return `
    <section class="aim-panel raise-panel">
      <h2>🔼 上げ狙い（${escapeHtml(String(sorted.length))}件）</h2>
      <p class="target-copy">前回大きく凹み＋同機種平均は上の台。main → sub、score順。</p>
      <div class="raise-grid">${rows}</div>
    </section>
  `;
}

function renderPatternsPanel(patterns) {
  if (!patterns || !patterns.stores) {
    return "";
  }
  const usable = (patterns.stores || []).filter(
    (s) => (s.days || 0) > 0 && (s.band_heat || []).length,
  );
  if (!usable.length) {
    return "";
  }
  const wdays = ["月", "火", "水", "木", "金", "土", "日"];
  const cards = usable
    .map((store) => {
      const heatHead =
        `<div class="heat-cell heat-label"></div>` +
        wdays
          .map((w) => `<div class="heat-cell heat-head">${escapeHtml(w)}</div>`)
          .join("");
      const heatRows = (store.band_heat || [])
        .map((b) => {
          const cells = (b.weekday || [])
            .map((c) => {
              const cls = patternHeatClass(c ? c.avg : null);
              return `<div class="heat-cell ${cls}">${escapeHtml(
                c && c.avg !== null ? String(Math.round(c.avg)) : "-",
              )}</div>`;
            })
            .join("");
          const pr = Math.max(0, Math.min(1, b.plus_rate || 0));
          return (
            `<div class="heat-cell heat-label">${escapeHtml(
              String(b.band),
            )}番台</div>${cells}` +
            `<div class="heat-meta">平均 ${escapeHtml(
              formatSignedNumber(b.overall_avg, "枚"),
            )}` +
            `<span class="pbar"><span class="pbar-fill" style="width:${(
              pr * 100
            ).toFixed(0)}%"></span></span>` +
            `P${escapeHtml(formatCoverageRate(b.plus_rate))}</div>`
          );
        })
        .join("");
      const cycleChips = (store.cycles || [])
        .map((c) => {
          const dots =
            "●".repeat(Math.min(Number(c.count) || 0, 8)) +
            "○".repeat(Math.max(0, 8 - (Number(c.count) || 0)));
          return (
            `<div class="cycle-chip"><strong>${escapeHtml(
              String(c.band),
            )}番台</strong> ` +
            `<span class="cycle-dots">${dots}</span> ` +
            `約${escapeHtml(formatPlainNumber(c.median_gap, "日"))}置き` +
            `（${escapeHtml(formatPlainNumber(c.count, "回"))}）</div>`
          );
        })
        .join("");
      const eventChips = (store.event_days || [])
        .filter((e) => e.label !== "その他")
        .map((e) => {
          const up = (e.delta || 0) >= 0;
          return `<div class="event-chip ${up ? "ev-up" : "ev-down"}">${escapeHtml(
            e.label,
          )} ${escapeHtml(formatSignedNumber(e.delta, "枚"))}</div>`;
        })
        .join("");
      const tailLines = wdays
        .filter((w) => (store.weekday_tails || {})[w])
        .map((w) => {
          const items = store.weekday_tails[w]
            .map(
              (t) =>
                `末尾${escapeHtml(String(t.tail))} ` +
                `${escapeHtml(formatSignedNumber(t.avg_diff, "枚"))}`,
            )
            .join(" ／ ");
          return `<li><strong>${escapeHtml(w)}</strong> ${items}</li>`;
        })
        .join("");
      return `
        <article class="pattern-store-card">
          <div class="badge-row">
            ${renderBadge(
              priorityDisplayLabel(store.priority_group),
              stateBadgeKind(store.priority_group === "main" ? "A" : "B"),
            )}
            ${renderBadge(`${store.days || 0}日`, "neutral")}
          </div>
          <h3 class="pattern-title">${escapeHtml(store.store_name || "-")}</h3>
          <h4 class="trend-subtitle">曜日ヒートマップ（濃いほど強い／数値=平均差枚）</h4>
          <div class="heat-grid">${heatHead}${heatRows}</div>
          <h4 class="trend-subtitle">イベント日（基準比）</h4>
          <div class="chip-row">${
            eventChips || '<span class="trend-caption">傾向なし</span>'
          }</div>
          <h4 class="trend-subtitle">出現周期（最強だった台番帯）</h4>
          <div class="cycle-list">${
            cycleChips || '<span class="trend-caption">該当なし</span>'
          }</div>
          <details class="focus-details">
            <summary>曜日別 強い末尾を開く</summary>
            <ul class="pattern-list">${tailLines}</ul>
          </details>
        </article>
      `;
    })
    .join("");
  return `
    <section class="trend-panel target-panel">
      <h2>傾向分析（曜日・周期・イベント日）</h2>
      <p class="target-copy">${escapeHtml(patterns.note || "")}</p>
      <p class="target-copy">
        集計期間: ${escapeHtml(patterns.coverage_window || "-")}
        ／ slorepo ${escapeHtml(String(patterns.requested_days || "-"))}日窓
      </p>
      <div class="pattern-grid">${cards}</div>
    </section>
  `;
}

function mountDashboard(payload, targets, trends, recent, patterns) {
  const root = document.getElementById("app");
  const notes = payload.notes || [];

  function render() {
    root.innerHTML = `
      <main class="page">
        ${renderHeroCard(payload, targets)}
        ${renderDailyTargetsPanel(patterns, targets)}
        ${renderRaisePanel(targets)}
        <details class="lowprio">
          <summary>機種・店舗別の詳細／傾向ヒートマップを開く</summary>
          ${renderTargetsPanel(targets)}
          ${renderPatternsPanel(patterns)}
          ${renderTrendsPanel(trends)}
          ${renderTomorrowRibbon(trends)}
          ${renderRecentMinrepoPanel(recent)}
        </details>
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

async function loadTrendsPayload() {
  try {
    const response = await fetch("./data/trends.json", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    return null;
  }
}

async function loadRecentMinrepoPayload() {
  try {
    const response = await fetch("./data/recent_minrepo.json", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    return null;
  }
}

async function loadPatternsPayload() {
  try {
    const response = await fetch("./data/patterns.json", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    return null;
  }
}

Promise.all([
  loadPayload(),
  loadTargetsPayload(),
  loadTrendsPayload(),
  loadRecentMinrepoPayload(),
  loadPatternsPayload(),
])
  .then(([payload, targets, trends, recent, patterns]) =>
    mountDashboard(payload, targets, trends, recent, patterns),
  )
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

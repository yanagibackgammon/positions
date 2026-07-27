"use strict";

const state = {
  positions: [],
  filtered: [],
  sortKey: "errorLoss",
  sortDirection: "desc",
};

const elements = {
  title: document.getElementById("page-title"),
  summary: document.getElementById("summary"),
  body: document.getElementById("positions-body"),
  visibleCount: document.getElementById("visible-count"),
  empty: document.getElementById("empty-state"),
  search: document.getElementById("search-input"),
  type: document.getElementById("type-filter"),
  classification: document.getElementById("class-filter"),
  file: document.getElementById("file-filter"),
  reset: document.getElementById("reset-button"),
  dialog: document.getElementById("board-dialog"),
  dialogImage: document.getElementById("dialog-image"),
  dialogClose: document.getElementById("dialog-close"),
};

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toRgb(hex) {
  const raw = String(hex || "#B7924B").replace("#", "");
  const normalized = raw.length === 3 ? raw.split("").map((c) => c + c).join("") : raw;
  return [0, 2, 4].map((offset) => Number.parseInt(normalized.slice(offset, offset + 2), 16));
}

function formatPercent(value) {
  return value == null || Number.isNaN(Number(value)) ? "—" : `${(Number(value) * 100).toFixed(2)}%`;
}

function formatLoss(value) {
  return value == null || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(3);
}

function formatEquity(value) {
  return value == null || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(3);
}

function numericCell(value, formatter, extraClass = "") {
  const empty = value == null || Number.isNaN(Number(value));
  return `<td class="number ${empty ? "empty" : ""} ${extraClass}">${formatter(value)}</td>`;
}

function candidateRows(position) {
  if (!position.candidates?.length) {
    return `<p>候補手データはありません。</p>`;
  }
  return `
    <div class="candidate-wrap">
      <table class="candidate-table">
        <thead><tr>
          <th>順位</th><th>アクション</th><th>ロス</th><th>勝率</th><th>G勝率</th><th>BG勝率</th><th>敗率</th><th>G負率</th><th>BG負率</th><th>Equity</th>
        </tr></thead>
        <tbody>
          ${position.candidates.map((candidate, index) => `
            <tr class="${index === 0 ? "best-candidate" : ""}">
              <td>${escapeHTML(candidate.rank)}</td>
              <td class="action">${escapeHTML(candidate.action)}</td>
              <td class="number">${formatLoss(candidate.equityLoss)}</td>
              <td class="number">${formatPercent(candidate.winRate)}</td>
              <td class="number">${formatPercent(candidate.gammonWinRate)}</td>
              <td class="number">${formatPercent(candidate.backgammonWinRate)}</td>
              <td class="number">${formatPercent(candidate.loseRate)}</td>
              <td class="number">${formatPercent(candidate.gammonLoseRate)}</td>
              <td class="number">${formatPercent(candidate.backgammonLoseRate)}</td>
              <td class="number">${formatEquity(candidate.equity)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

function detailRow(position) {
  return `
    <tr class="detail-row" id="detail-${escapeHTML(position.id)}" hidden>
      <td colspan="12">
        <div class="detail-panel">
          <div class="detail-meta">
            <dl>
              <dt>Position ID</dt><dd>${escapeHTML(position.id)}</dd>
              <dt>Player</dt><dd>${escapeHTML(position.player)}</dd>
              <dt>Opponent</dt><dd>${escapeHTML(position.opponent)}</dd>
              <dt>Source</dt><dd>${escapeHTML(position.sourceFile)}</dd>
              <dt>Score</dt><dd>${escapeHTML(position.playerScore)}–${escapeHTML(position.opponentScore)} / ${escapeHTML(position.matchLength)}pt</dd>
              <dt>Decision</dt><dd>Game ${escapeHTML(position.gameNumber)} / ${escapeHTML(position.moveNumber)}</dd>
              <dt>Dice</dt><dd>${escapeHTML(position.dice)}</dd>
              <dt>XGID</dt><dd>${escapeHTML(position.xgid)}</dd>
            </dl>
            <button class="copy-button" type="button" data-copy="${escapeHTML(position.xgid)}">XGIDをコピー</button>
          </div>
          ${candidateRows(position)}
        </div>
      </td>
    </tr>`;
}

function rowHTML(position) {
  const badgeClass = position.classification.toLowerCase();
  return `
    <tr class="main-row">
      <td>
        <button class="board-button" type="button" data-board="${escapeHTML(position.boardImage)}" aria-label="盤面を拡大">
          <img src="${escapeHTML(position.boardImage)}" alt="${escapeHTML(position.id)} の盤面" loading="lazy">
        </button>
      </td>
      <td><span class="badge ${badgeClass}">${escapeHTML(position.classification)}</span></td>
      <td><span class="type-label ${escapeHTML(position.decisionType)}">${escapeHTML(position.decisionLabel)}</span></td>
      <td>
        <div class="match-name" title="${escapeHTML(position.sourceFile)}">${escapeHTML(position.sourceFile)}</div>
        <div class="match-players">${escapeHTML(position.player)} vs ${escapeHTML(position.opponent)}</div>
      </td>
      <td>
        <div class="position-number">G${escapeHTML(position.gameNumber)} / #${escapeHTML(position.moveNumber)}</div>
        <div class="position-score">${escapeHTML(position.playerScore)}–${escapeHTML(position.opponentScore)} · ${escapeHTML(position.dice)}</div>
        <button class="detail-toggle" type="button" data-detail="${escapeHTML(position.id)}">解析詳細</button>
      </td>
      <td class="action">${escapeHTML(position.playedAction)}</td>
      <td class="action">${escapeHTML(position.bestAction)}</td>
      ${numericCell(position.errorLoss, formatLoss, "loss")}
      ${numericCell(position.winRate, formatPercent)}
      ${numericCell(position.gammonWinRate, formatPercent)}
      ${numericCell(position.loseRate, formatPercent)}
      ${numericCell(position.gammonLoseRate, formatPercent)}
    </tr>
    ${detailRow(position)}`;
}

function compareValues(a, b, key, type) {
  const av = a[key];
  const bv = b[key];
  const aEmpty = av == null || (type === "number" && Number.isNaN(Number(av)));
  const bEmpty = bv == null || (type === "number" && Number.isNaN(Number(bv)));
  if (aEmpty && bEmpty) return 0;
  if (aEmpty) return 1;
  if (bEmpty) return -1;
  if (type === "number") return Number(av) - Number(bv);
  return String(av).localeCompare(String(bv), "ja", { numeric: true, sensitivity: "base" });
}

function sortPositions(positions) {
  const heading = document.querySelector(`th[data-key="${CSS.escape(state.sortKey)}"]`);
  const type = heading?.dataset.type || "text";
  return [...positions].sort((a, b) => {
    const result = compareValues(a, b, state.sortKey, type);
    return state.sortDirection === "asc" ? result : -result;
  });
}

function filterPositions() {
  const query = elements.search.value.trim().toLocaleLowerCase("ja");
  state.filtered = state.positions.filter((position) => {
    if (elements.type.value && position.decisionType !== elements.type.value) return false;
    if (elements.classification.value && position.classification !== elements.classification.value) return false;
    if (elements.file.value && position.sourceFile !== elements.file.value) return false;
    if (!query) return true;
    const haystack = [
      position.id, position.player, position.opponent, position.sourceFile,
      position.playedAction, position.bestAction, position.xgid,
      position.decisionLabel, position.classification,
    ].join(" ").toLocaleLowerCase("ja");
    return haystack.includes(query);
  });
  render();
}

function render() {
  const positions = sortPositions(state.filtered);
  elements.body.innerHTML = positions.map(rowHTML).join("");
  elements.visibleCount.textContent = `${positions.length} positions`;
  elements.empty.hidden = positions.length !== 0;

  document.querySelectorAll("th[data-key]").forEach((th) => {
    th.classList.remove("is-sorted", "desc");
    if (th.dataset.key === state.sortKey) {
      th.classList.add("is-sorted");
      if (state.sortDirection === "desc") th.classList.add("desc");
    }
  });
}

function installEvents() {
  [elements.search, elements.type, elements.classification, elements.file].forEach((element) => {
    element.addEventListener(element === elements.search ? "input" : "change", filterPositions);
  });

  elements.reset.addEventListener("click", () => {
    elements.search.value = "";
    elements.type.value = "";
    elements.classification.value = "";
    elements.file.value = "";
    state.sortKey = "errorLoss";
    state.sortDirection = "desc";
    filterPositions();
  });

  document.querySelectorAll("th[data-key] button").forEach((button) => {
    button.addEventListener("click", () => {
      const th = button.closest("th");
      const key = th.dataset.key;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = th.dataset.type === "number" ? "desc" : "asc";
      }
      render();
    });
  });

  elements.body.addEventListener("click", async (event) => {
    const boardButton = event.target.closest("[data-board]");
    if (boardButton) {
      elements.dialogImage.src = boardButton.dataset.board;
      elements.dialog.showModal();
      return;
    }

    const detailButton = event.target.closest("[data-detail]");
    if (detailButton) {
      const detail = document.getElementById(`detail-${detailButton.dataset.detail}`);
      detail.hidden = !detail.hidden;
      detailButton.textContent = detail.hidden ? "解析詳細" : "詳細を閉じる";
      return;
    }

    const copyButton = event.target.closest("[data-copy]");
    if (copyButton) {
      await navigator.clipboard.writeText(copyButton.dataset.copy);
      const original = copyButton.textContent;
      copyButton.textContent = "コピーしました";
      setTimeout(() => { copyButton.textContent = original; }, 1200);
    }
  });

  elements.dialogClose.addEventListener("click", () => elements.dialog.close());
  elements.dialog.addEventListener("click", (event) => {
    if (event.target === elements.dialog) elements.dialog.close();
  });
}

async function start() {
  try {
    const response = await fetch(`data/positions.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.positions = payload.positions || [];
    state.filtered = [...state.positions];

    const title = payload.meta?.title || "Backgammon Error Positions";
    document.title = title;
    elements.title.textContent = title;
    elements.summary.textContent = `${payload.meta?.sourceFileCount || 0}棋譜から ${state.positions.length}件を抽出 · Error ≥ ${Number(payload.meta?.errorThreshold || 0).toFixed(3)} · Blunder ≥ ${Number(payload.meta?.blunderThreshold || 0).toFixed(3)}`;

    const theme = payload.meta?.themeColor || "#B7924B";
    const [r, g, b] = toRgb(theme);
    document.documentElement.style.setProperty("--theme", theme);
    document.documentElement.style.setProperty("--theme-rgb", `${r}, ${g}, ${b}`);

    [...new Set(state.positions.map((position) => position.sourceFile))]
      .sort((a, b) => a.localeCompare(b, "ja", { numeric: true }))
      .forEach((filename) => {
        const option = document.createElement("option");
        option.value = filename;
        option.textContent = filename;
        elements.file.append(option);
      });

    installEvents();
    render();
  } catch (error) {
    console.error(error);
    elements.summary.textContent = "データの読み込みに失敗しました。GitHub Actionsの実行結果を確認してください。";
    elements.empty.hidden = false;
    elements.empty.textContent = "positions.jsonを読み込めませんでした。";
  }
}

start();

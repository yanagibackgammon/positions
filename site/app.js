"use strict";

const state = {
  positions: [],
  filtered: [],
};

const elements = {
  title: document.getElementById("page-title"),
  body: document.getElementById("positions-body"),
  visibleCount: document.getElementById("visible-count"),
  empty: document.getElementById("empty-state"),
  type: document.getElementById("type-filter"),
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

function numericCell(value) {
  const empty = value == null || Number.isNaN(Number(value));
  return `<td class="number ${empty ? "empty" : ""}">${formatPercent(value)}</td>`;
}

function rowHTML(position) {
  return `
    <tr class="main-row">
      <td>
        <button class="board-button" type="button" data-board="${escapeHTML(position.boardImage)}" aria-label="盤面を拡大">
          <img src="${escapeHTML(position.boardImage)}" alt="${escapeHTML(position.id)} の盤面" loading="lazy">
        </button>
      </td>
      <td class="action">${escapeHTML(position.bestAction)}</td>
      <td class="score">
        <strong>${escapeHTML(position.playerScore)}-${escapeHTML(position.opponentScore)} / ${escapeHTML(position.matchLength)}pt</strong>
        <span>${escapeHTML(position.sourceFile)}</span>
        <span>G${escapeHTML(position.gameNumber)} · #${escapeHTML(position.moveNumber)}${position.dice && position.dice !== '—' ? ` · Dice ${escapeHTML(position.dice)}` : ''}</span>
      </td>
      ${numericCell(position.winRate)}
      ${numericCell(position.gammonWinRate)}
      ${numericCell(position.backgammonWinRate)}
      ${numericCell(position.loseRate)}
      ${numericCell(position.gammonLoseRate)}
    </tr>`;
}

function filterPositions() {
  state.filtered = state.positions.filter((position) => {
    if (elements.type.value && position.decisionType !== elements.type.value) return false;
    return true;
  });
  render();
}

function render() {
  elements.body.innerHTML = state.filtered.map(rowHTML).join("");
  elements.visibleCount.textContent = `${state.filtered.length} positions`;
  elements.empty.hidden = state.filtered.length !== 0;
}

function installEvents() {
  elements.type.addEventListener("change", filterPositions);

  elements.body.addEventListener("click", (event) => {
    const boardButton = event.target.closest("[data-board]");
    if (boardButton) {
      elements.dialogImage.src = boardButton.dataset.board;
      elements.dialog.showModal();
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

    const theme = payload.meta?.themeColor || "#B7924B";
    const [r, g, b] = toRgb(theme);
    document.documentElement.style.setProperty("--theme", theme);
    document.documentElement.style.setProperty("--theme-rgb", `${r}, ${g}, ${b}`);

    installEvents();
    render();
  } catch (error) {
    console.error(error);
    elements.empty.hidden = false;
    elements.empty.textContent = "positions.jsonを読み込めませんでした。GitHub Actionsの実行結果を確認してください。";
  }
}

start();

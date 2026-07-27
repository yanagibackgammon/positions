"use strict";

const state = {
  positions: [],
  filtered: [],
  sortKey: null,
  sortDirection: "asc",
};

const elements = {
  title: document.getElementById("page-title"),
  boardHeader: document.getElementById("board-header"),
  body: document.getElementById("positions-body"),
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
  return value == null || Number.isNaN(Number(value)) ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
}

function numericCell(value) {
  const empty = value == null || Number.isNaN(Number(value));
  return `<td class="number ${empty ? "empty" : ""}">${formatPercent(value)}</td>`;
}

function awayLabel(position, away) {
  if (position.isCrawford && away === 1) return "Crawford";
  return `${away}away`;
}

function scoreCell(value, away = null, position = null) {
  const sub = away == null || !position
    ? ""
    : `<span class="score-away ${position.isCrawford && away === 1 ? "crawford" : ""}">${awayLabel(position, away)}</span>`;
  return `<td><div class="score-value">${escapeHTML(value)}</div>${sub}</td>`;
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
      ${scoreCell(position.matchLength)}
      ${scoreCell(position.playerScore, position.playerAway, position)}
      ${scoreCell(position.opponentScore, position.opponentAway, position)}
      ${numericCell(position.winRate)}
      ${numericCell(position.gammonWinRate)}
      ${numericCell(position.loseRate)}
      ${numericCell(position.gammonLoseRate)}
    </tr>`;
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

function sortedPositions() {
  if (!state.sortKey) return [...state.filtered];
  const heading = document.querySelector(`th[data-key="${CSS.escape(state.sortKey)}"]`);
  const type = heading?.dataset.type || "text";
  return [...state.filtered].sort((a, b) => {
    const result = compareValues(a, b, state.sortKey, type);
    return state.sortDirection === "asc" ? result : -result;
  });
}

function filterPositions() {
  state.filtered = state.positions.filter((position) => !elements.type.value || position.decisionType === elements.type.value);
  render();
}

function render() {
  const positions = sortedPositions();
  elements.body.innerHTML = positions.map(rowHTML).join("");
  elements.boardHeader.textContent = `${positions.length} positions`;
  elements.empty.hidden = positions.length !== 0;

  document.querySelectorAll("th[data-key]").forEach((heading) => {
    heading.classList.remove("is-sorted", "desc");
    if (heading.dataset.key === state.sortKey) {
      heading.classList.add("is-sorted");
      if (state.sortDirection === "desc") heading.classList.add("desc");
    }
  });
}

function installEvents() {
  elements.type.addEventListener("change", filterPositions);

  document.querySelectorAll("th[data-key] button").forEach((button) => {
    button.addEventListener("click", () => {
      const heading = button.closest("th");
      const key = heading.dataset.key;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = "asc";
      }
      render();
    });
  });

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
    state.positions = (payload.positions || []).map((position) => ({
      ...position,
      playerAway: Math.max(0, Number(position.matchLength) - Number(position.playerScore)),
      opponentAway: Math.max(0, Number(position.matchLength) - Number(position.opponentScore)),
    }));
    state.filtered = [...state.positions];

    const title = payload.meta?.title || "Backgammon Positions";
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

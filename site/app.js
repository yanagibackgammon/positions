"use strict";

const state = {
  positions: [],
  filtered: [],
  sortKey: null,
  sortDirection: "asc",
  baseTitle: "Backgammon",
};

const elements = {
  title: document.getElementById("page-title"),
  header: document.querySelector(".page-header"),
  body: document.getElementById("positions-body"),
  empty: document.getElementById("empty-state"),
  type: document.getElementById("type-filter"),
  dialog: document.getElementById("board-dialog"),
  dialogImage: document.getElementById("dialog-image"),
  dialogSource: document.getElementById("dialog-source"),
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

function awayText(position, away) {
  if (position.isCrawford && away === 1) return "Cr";
  if (position.isPostCrawford && away === 1) return "PC";
  return `${away}a`;
}

function cubeStateText(position) {
  if (position.isCrawford) return "Cr";
  if (position.cubeValue == null || position.cubeValue === "") return "—";
  return String(position.cubeValue);
}

function normalizeRate(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return Math.max(0, Math.min(1, num));
}

function pipCounts(position) {
  const points = Array.isArray(position.position) ? position.position : [];
  let black = 0;
  let white = 0;

  for (let point = 1; point <= 24; point += 1) {
    const value = Number(points[point] || 0);
    if (value > 0) black += value * point;
    if (value < 0) white += Math.abs(value) * (25 - point);
  }

  black += Math.abs(Number(points[25] || 0)) * 25;
  white += Math.abs(Number(points[0] || 0)) * 25;

  return { black, white };
}

function scoreAwayMarkup(score, awayLabel) {
  return `
    <span class="stat-value score-value">${escapeHTML(score)}</span>
    <span class="stat-note">(${escapeHTML(awayLabel)})</span>`;
}

function statLine(label, valueMarkup, sideClass = "") {
  return `
    <div class="stat-line ${sideClass}">
      <span class="stat-label">${escapeHTML(label)}</span>
      <span class="stat-main">${valueMarkup}</span>
    </div>`;
}

function centerValueLine(valueMarkup, sideClass = "") {
  return `
    <div class="stat-line ${sideClass}">
      <span class="stat-main">${valueMarkup}</span>
    </div>`;
}

function summaryCell(position) {
  const blackWin = normalizeRate(position.winRate);
  const blackGammon = normalizeRate(position.gammonWinRate);
  const whiteWin = normalizeRate(position.loseRate);
  const whiteGammon = normalizeRate(position.gammonLoseRate);

  const blackWidth = blackWin == null ? 50 : blackWin * 100;
  const whiteWidth = whiteWin == null ? Math.max(0, 100 - blackWidth) : whiteWin * 100;
  const blackOverlay = blackGammon == null ? 0 : blackGammon * 100;
  const whiteOverlay = whiteGammon == null ? 0 : whiteGammon * 100;

  return `
    <td class="summary-cell">
      <div class="summary-top">
        <div class="summary-side summary-black">
          ${statLine("BK", scoreAwayMarkup(position.playerScore, awayText(position, position.playerAway)), "title-line")}
          ${statLine("PIP", `<span class="stat-value">${escapeHTML(position.blackPip)}</span>`)}
          ${statLine("W", `<span class="stat-value">${escapeHTML(formatPercent(position.winRate))}</span>`)}
          ${statLine("GW", `<span class="stat-value">${escapeHTML(formatPercent(position.gammonWinRate))}</span>`)}
        </div>
        <div class="summary-middle">
          ${statLine("ML", `<span class="stat-value">${escapeHTML(position.matchLength)}</span>`, "center-line")}
          ${statLine("CB", `<span class="stat-value">${escapeHTML(cubeStateText(position))}</span>`, "center-line cube-line")}
        </div>
        <div class="summary-side summary-white">
          ${statLine("WH", scoreAwayMarkup(position.opponentScore, awayText(position, position.opponentAway)), "title-line")}
          ${statLine("PIP", `<span class="stat-value">${escapeHTML(position.whitePip)}</span>`)}
          ${statLine("W", `<span class="stat-value">${escapeHTML(formatPercent(position.loseRate))}</span>`)}
          ${statLine("GW", `<span class="stat-value">${escapeHTML(formatPercent(position.gammonLoseRate))}</span>`)}
        </div>
      </div>
      <div class="win-scale" aria-hidden="true">
        <span style="left:30%">30%</span>
        <span style="left:50%">50%</span>
        <span style="left:70%">70%</span>
        <span class="win-boundary-marker" style="left:${blackWidth.toFixed(3)}%">▼</span>
      </div>
      <div class="win-bar" aria-hidden="true">
        <div class="win-black" style="width:${blackWidth.toFixed(3)}%"></div>
        <div class="win-white" style="width:${whiteWidth.toFixed(3)}%"></div>
        <div class="win-black-gammon" style="width:${Math.min(blackOverlay, blackWidth).toFixed(3)}%"></div>
        <div class="win-white-gammon" style="width:${Math.min(whiteOverlay, whiteWidth).toFixed(3)}%"></div>
      </div>
    </td>`;
}

function rowHTML(position) {
  return `
    <tr class="main-row">
      <td class="board-cell">
        <button class="board-button" type="button" data-board="${escapeHTML(position.boardImage)}" data-source="${escapeHTML(position.sourceFile || "")}" aria-label="盤面を拡大">
          <img src="${escapeHTML(position.boardImage)}" alt="${escapeHTML(position.id)} の盤面" loading="lazy">
        </button>
      </td>
      ${actionCell(position)}
      ${summaryCell(position)}
    </tr>`;
}


function formatError(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return `−${Math.abs(number).toFixed(3)}`;
}

function formatSignedEquity(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  const sign = number >= 0 ? "+" : "−";
  return `${sign}${Math.abs(number).toFixed(3)}`;
}

function cubeActionCell(position) {
  const outcomes = (Array.isArray(position.candidates) ? position.candidates : [])
    .filter((candidate) => candidate && candidate.action)
    .slice(0, 3);

  const rows = [
    `<div class="action-option is-best cube-best-action">
      <span class="action-text">${escapeHTML(position.bestAction || "—")}</span>
      <span class="action-error"></span>
    </div>`,
    ...outcomes.map((candidate) => `
      <div class="action-option cube-outcome">
        <span class="action-text">${escapeHTML(candidate.action || "—")}</span>
        <span class="action-error">${escapeHTML(formatSignedEquity(candidate.equityDifference))}</span>
      </div>`),
  ].join("");

  return `<td class="action-cell"><div class="action-list">${rows}</div></td>`;
}

function actionCell(position) {
  if (position.decisionType === "cube") return cubeActionCell(position);
  const sourceCandidates = Array.isArray(position.candidates) ? position.candidates : [];
  const orderedCandidates = sourceCandidates
    .filter((candidate) => {
      const loss = Number(candidate?.equityLoss);
      return Number.isFinite(loss) && loss >= 0 && loss < 100;
    })
    .slice()
    .sort((a, b) => Number(a.rank || 0) - Number(b.rank || 0));
  const candidates = orderedCandidates.slice(0, 3);

  if (!candidates.length) {
    candidates.push({ rank: 1, action: position.bestAction, equityLoss: 0 });
  }

  const playedAction = String(position.playedAction || "").trim();
  const playedIsVisible = candidates.some((candidate) => String(candidate.action || "").trim() === playedAction);
  if (playedAction && !playedIsVisible) {
    const playedCandidate = orderedCandidates.find(
      (candidate) => String(candidate.action || "").trim() === playedAction,
    );
    const candidateLoss = Number(playedCandidate?.equityLoss);
    candidates.push({
      rank: playedCandidate?.rank ?? 4,
      action: playedAction,
      equityLoss: Number.isFinite(candidateLoss) && candidateLoss >= 0 && candidateLoss < 100
        ? candidateLoss
        : position.errorLoss,
      isPlayedError: true,
    });
  }

  const rows = candidates.map((candidate, index) => {
    const isBest = index === 0 || Number(candidate.rank) === 1;
    const error = isBest ? "" : formatError(candidate.equityLoss);
    const playedClass = candidate.isPlayedError ? " is-played-error" : "";
    return `
      <div class="action-option ${isBest ? "is-best" : ""}${playedClass}">
        <span class="action-text">${escapeHTML(candidate.action || "—")}</span>
        <span class="action-error">${escapeHTML(error)}</span>
      </div>`;
  }).join("");

  return `<td class="action-cell"><div class="action-list">${rows}</div></td>`;
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
  const control = document.querySelector(`[data-sort-key="${CSS.escape(state.sortKey)}"]`);
  const type = control?.dataset.sortType || "text";
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
  const pageTitle = `${state.baseTitle} ${positions.length} Positions`;
  elements.title.textContent = pageTitle;
  document.title = "Backgammon Positions";
  elements.empty.hidden = positions.length !== 0;

  document.querySelectorAll("[data-sort-key]").forEach((control) => {
    control.classList.remove("is-sorted", "desc");
    if (control.dataset.sortKey === state.sortKey) {
      control.classList.add("is-sorted");
      if (state.sortDirection === "desc") control.classList.add("desc");
    }
  });
}

function installOverscrollGuard() {
  let lastTouchX = 0;
  let lastTouchY = 0;

  document.addEventListener("touchstart", (event) => {
    if (event.touches.length !== 1) return;
    lastTouchX = event.touches[0].clientX;
    lastTouchY = event.touches[0].clientY;
  }, { passive: true });

  document.addEventListener("touchmove", (event) => {
    if (event.touches.length !== 1) return;

    const touch = event.touches[0];
    const deltaX = touch.clientX - lastTouchX;
    const deltaY = touch.clientY - lastTouchY;
    lastTouchX = touch.clientX;
    lastTouchY = touch.clientY;

    if (Math.abs(deltaY) <= Math.abs(deltaX)) return;

    const scroller = document.scrollingElement || document.documentElement;
    const atTop = scroller.scrollTop <= 0;
    const atBottom = Math.ceil(scroller.scrollTop + scroller.clientHeight) >= scroller.scrollHeight;

    if ((atTop && deltaY > 0) || (atBottom && deltaY < 0)) {
      event.preventDefault();
    }
  }, { passive: false });
}

function installMobileHeaderBehavior() {
  const mobileQuery = window.matchMedia("(max-width: 760px)");
  let lastScrollY = window.scrollY;
  let ticking = false;

  const setTitleVisible = (visible) => {
    document.body.classList.toggle("mobile-title-visible", visible);
    document.body.classList.toggle("mobile-title-hidden", !visible);
  };

  const update = () => {
    const currentScrollY = Math.max(0, window.scrollY);
    if (!mobileQuery.matches) {
      document.body.classList.remove("mobile-title-visible", "mobile-title-hidden");
      lastScrollY = currentScrollY;
      ticking = false;
      return;
    }

    const delta = currentScrollY - lastScrollY;
    if (currentScrollY <= 2 || delta < -6) {
      setTitleVisible(true);
    } else if (delta > 6 && currentScrollY > 32) {
      setTitleVisible(false);
    }

    lastScrollY = currentScrollY;
    ticking = false;
  };

  const requestUpdate = () => {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(update);
  };

  if (mobileQuery.matches) {
    setTitleVisible(true);
  } else {
    document.body.classList.remove("mobile-title-visible", "mobile-title-hidden");
  }
  window.addEventListener("scroll", requestUpdate, { passive: true });
  mobileQuery.addEventListener?.("change", requestUpdate);
}

function scrollToTopFromTitle() {
  document.body.classList.add("mobile-title-visible");
  document.body.classList.remove("mobile-title-hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function installEvents() {
  installOverscrollGuard();
  installMobileHeaderBehavior();
  elements.type.addEventListener("change", filterPositions);
  elements.title.addEventListener("click", scrollToTopFromTitle);
  elements.title.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      scrollToTopFromTitle();
    }
  });

  document.querySelectorAll("[data-sort-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.sortKey;
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
      elements.dialogSource.textContent = boardButton.dataset.source || "";
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
    state.positions = (payload.positions || []).map((position) => {
      const pips = pipCounts(position);
      return {
        ...position,
        playerAway: Math.max(0, Number(position.matchLength) - Number(position.playerScore)),
        opponentAway: Math.max(0, Number(position.matchLength) - Number(position.opponentScore)),
        blackPip: pips.black,
        whitePip: pips.white,
        isCrawford: Boolean(position.isCrawford),
        isPostCrawford: Boolean(position.isPostCrawford),
        cubeSortValue: position.isCrawford ? 0 : Number(position.cubeValue || 0),
      };
    });
    state.filtered = [...state.positions];

    const configuredTitle = payload.meta?.title || "Backgammon Positions";
    state.baseTitle = configuredTitle.replace(/\s+Positions$/i, "") || "Backgammon";

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

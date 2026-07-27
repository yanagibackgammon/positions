#!/usr/bin/env python3
"""Build the static backgammon error-position database from imports/*.xg."""

from __future__ import annotations

import hashlib
import html
import json
import math
import shutil
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

import xgread  # noqa: E402
from xgread import CubeAction, Evaluation, Move  # noqa: E402

IMPORTS_DIR = ROOT / "imports"
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"
BOARD_DIR = DIST_DIR / "assets" / "boards"
DATA_DIR = DIST_DIR / "data"
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "databaseTitle": "Backgammon Error Positions",
        "targetPlayers": [],
        "errorThreshold": 0.02,
        "blunderThreshold": 0.08,
        "includeCheckerErrors": True,
        "includeCubeErrors": True,
        "includeTakeErrors": True,
        "anonymizeOpponents": False,
        "themeColor": "#B7924B",
    }
    if not CONFIG_PATH.exists():
        return defaults
    loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {**defaults, **loaded}


def player_name(match: Any, sign: int) -> str:
    return match.header.player1 if sign == 1 else match.header.player2


def target_enabled(name: str, targets: set[str]) -> bool:
    return not targets or name.casefold() in targets


def classification(loss: float, blunder_threshold: float) -> str:
    return "Blunder" if loss >= blunder_threshold else "Error"


def probability_fields(evaluation: Evaluation | None, invert: bool = False) -> dict[str, float | None]:
    if evaluation is None:
        return {
            "winRate": None,
            "gammonWinRate": None,
            "backgammonWinRate": None,
            "loseRate": None,
            "gammonLoseRate": None,
            "backgammonLoseRate": None,
            "equity": None,
        }

    # XG stores these fields cumulatively: win_single is total wins, win_gammon
    # includes backgammons, and lose_single is total losses.
    if invert:
        return {
            "winRate": evaluation.lose_single,
            "gammonWinRate": evaluation.lose_gammon,
            "backgammonWinRate": evaluation.lose_bg,
            "loseRate": evaluation.win_single,
            "gammonLoseRate": evaluation.win_gammon,
            "backgammonLoseRate": evaluation.win_bg,
            "equity": -evaluation.equity,
        }

    return {
        "winRate": evaluation.win_single,
        "gammonWinRate": evaluation.win_gammon,
        "backgammonWinRate": evaluation.win_bg,
        "loseRate": evaluation.lose_single,
        "gammonLoseRate": evaluation.lose_gammon,
        "backgammonLoseRate": evaluation.lose_bg,
        "equity": evaluation.equity,
    }


def event_id(match_hash: str, game_number: int, move_number: int, decision_type: str, actor: str) -> str:
    raw = f"{match_hash}|{game_number}|{move_number}|{decision_type}|{actor.casefold()}"
    return "POS-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


def score_for_sign(decision: Any, sign: int) -> tuple[int, int]:
    if sign == 1:
        return decision.score1, decision.score2
    return decision.score2, decision.score1


def cube_value_number(cube_value: int) -> int:
    return 1 if cube_value == 0 else 2 ** abs(cube_value)


def compact_move_notation(notation: str) -> str:
    """Collapse repeated identical checker moves, e.g. 8/4 8/4 8/4 -> 8/4(3)."""
    tokens = str(notation).split()
    if len(tokens) < 2:
        return str(notation)

    counts: dict[str, int] = {}
    order: list[str] = []
    for token in tokens:
        if token not in counts:
            counts[token] = 0
            order.append(token)
        counts[token] += 1

    return " ".join(
        f"{token}({counts[token]})" if counts[token] > 1 else token
        for token in order
    )


def candidate_payload(move: Move) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, candidate in enumerate(move.candidates, start=1):
        rows.append(
            {
                "rank": rank,
                "action": compact_move_notation(xgread.format_moves(candidate.moves, move.position_before)),
                "equityLoss": candidate.equity_loss,
                **probability_fields(candidate.evaluation),
            }
        )
    return rows


def make_checker_row(match: Any, decision: Any, move: Move, cfg: dict[str, Any]) -> dict[str, Any] | None:
    actor = player_name(match, move.player)
    targets = {str(v).casefold() for v in cfg["targetPlayers"]}
    if not target_enabled(actor, targets) or not cfg["includeCheckerErrors"]:
        return None

    played_index = move.played_index
    played_candidate = move.candidates[played_index] if played_index is not None else None
    if played_candidate is not None:
        loss = max(0.0, float(played_candidate.equity_loss))
        actual_evaluation = played_candidate.evaluation
    else:
        loss = abs(float(move.error)) if move.is_analysed else 0.0
        actual_evaluation = move.analysis

    if loss + 1e-12 < float(cfg["errorThreshold"]):
        return None

    best_action = (
        compact_move_notation(xgread.format_moves(move.candidates[0].moves, move.position_before))
        if move.candidates
        else "—"
    )
    actor_score, opponent_score = score_for_sign(decision, move.player)
    opponent = player_name(match, -move.player)
    row_id = event_id(match.identity_hash, decision.game_number, decision.move_number, "checker", actor)

    return {
        "id": row_id,
        "decisionType": "checker",
        "decisionLabel": "Checker Play",
        "classification": classification(loss, float(cfg["blunderThreshold"])),
        "errorLoss": loss,
        "player": actor,
        "opponent": opponent,
        "onRollPlayer": actor,
        "onRollOpponent": opponent,
        "sourceFile": "",
        "matchId": match.identity_hash,
        "matchLength": match.header.match_length,
        "gameNumber": decision.game_number,
        "moveNumber": decision.move_number,
        "playerScore": actor_score,
        "opponentScore": opponent_score,
        "onRollScore": actor_score,
        "onRollOpponentScore": opponent_score,
        "dice": f"{move.dice[0]}{move.dice[1]}",
        "diceValues": list(move.dice),
        "playedAction": compact_move_notation(move.notation),
        "bestAction": best_action,
        "xgid": decision.xgid,
        "cubeValue": cube_value_number(move.cube_value),
        "cubeOwner": "center" if move.cube_value == 0 else ("onRoll" if move.cube_value > 0 else "opponent"),
        "position": list(move.position_before.points),
        "candidates": candidate_payload(move),
        **probability_fields(actual_evaluation),
        "matchDate": match.header.date.date().isoformat() if match.header.date else None,
    }


def best_double_action(cube: CubeAction) -> str:
    effective_double = min(cube.double_take_equity, cube.double_drop_equity)
    return "Double" if effective_double > cube.no_double_equity else "No Double"


def make_double_row(match: Any, decision: Any, cube: CubeAction, cfg: dict[str, Any]) -> dict[str, Any] | None:
    actor_sign = cube.player
    actor = player_name(match, actor_sign)
    targets = {str(v).casefold() for v in cfg["targetPlayers"]}
    if not target_enabled(actor, targets) or not cfg["includeCubeErrors"]:
        return None

    loss = abs(float(cube.error_double))
    if cube.error_double == xgread.NOT_ANALYSED or loss + 1e-12 < float(cfg["errorThreshold"]):
        return None

    actual = "Double" if cube.doubled else "No Double"
    if not cube.doubled:
        actual_eval: Evaluation | None = cube.no_double_analysis
    elif cube.took:
        actual_eval = cube.double_take_analysis
    else:
        actual_eval = None

    actor_score, opponent_score = score_for_sign(decision, actor_sign)
    opponent = player_name(match, -actor_sign)
    row_id = event_id(match.identity_hash, decision.game_number, decision.move_number, "double", actor)
    return {
        "id": row_id,
        "decisionType": "double",
        "decisionLabel": "Double Decision",
        "classification": classification(loss, float(cfg["blunderThreshold"])),
        "errorLoss": loss,
        "player": actor,
        "opponent": opponent,
        "onRollPlayer": actor,
        "onRollOpponent": opponent,
        "sourceFile": "",
        "matchId": match.identity_hash,
        "matchLength": match.header.match_length,
        "gameNumber": decision.game_number,
        "moveNumber": decision.move_number,
        "playerScore": actor_score,
        "opponentScore": opponent_score,
        "onRollScore": actor_score,
        "onRollOpponentScore": opponent_score,
        "dice": "—",
        "diceValues": [],
        "playedAction": actual,
        "bestAction": best_double_action(cube),
        "xgid": decision.xgid,
        "cubeValue": cube_value_number(cube.cube_value),
        "cubeOwner": "center" if cube.cube_value == 0 else ("onRoll" if cube.cube_value > 0 else "opponent"),
        "position": list(cube.position.points),
        "candidates": [
            {"rank": 1, "action": "No Double", "equity": cube.no_double_equity, **probability_fields(cube.no_double_analysis)},
            {"rank": 2, "action": "Double / Take", "equity": cube.double_take_equity, **probability_fields(cube.double_take_analysis)},
            {"rank": 3, "action": "Double / Pass", "equity": cube.double_drop_equity, **probability_fields(None)},
        ],
        **probability_fields(actual_eval),
        "matchDate": match.header.date.date().isoformat() if match.header.date else None,
    }


def make_take_row(match: Any, decision: Any, cube: CubeAction, cfg: dict[str, Any]) -> dict[str, Any] | None:
    if not cube.doubled or cube.took is None or not cfg["includeTakeErrors"]:
        return None

    actor_sign = -cube.player
    actor = player_name(match, actor_sign)
    targets = {str(v).casefold() for v in cfg["targetPlayers"]}
    if not target_enabled(actor, targets):
        return None

    loss = abs(float(cube.error_take))
    if cube.error_take == xgread.NOT_ANALYSED or loss + 1e-12 < float(cfg["errorThreshold"]):
        return None

    actual = "Take" if cube.took else "Pass"
    best = "Take" if cube.double_take_equity < cube.double_drop_equity else "Pass"
    actual_eval = cube.double_take_analysis if cube.took else None
    actor_score, opponent_score = score_for_sign(decision, actor_sign)
    opponent = player_name(match, -actor_sign)
    on_roll = player_name(match, cube.player)
    on_roll_opponent = player_name(match, -cube.player)
    on_roll_score, on_roll_opp_score = score_for_sign(decision, cube.player)
    row_id = event_id(match.identity_hash, decision.game_number, decision.move_number, "take", actor)

    return {
        "id": row_id,
        "decisionType": "take",
        "decisionLabel": "Take / Pass",
        "classification": classification(loss, float(cfg["blunderThreshold"])),
        "errorLoss": loss,
        "player": actor,
        "opponent": opponent,
        "onRollPlayer": on_roll,
        "onRollOpponent": on_roll_opponent,
        "sourceFile": "",
        "matchId": match.identity_hash,
        "matchLength": match.header.match_length,
        "gameNumber": decision.game_number,
        "moveNumber": decision.move_number,
        "playerScore": actor_score,
        "opponentScore": opponent_score,
        "onRollScore": on_roll_score,
        "onRollOpponentScore": on_roll_opp_score,
        "dice": "—",
        "diceValues": [],
        "playedAction": actual,
        "bestAction": best,
        "xgid": decision.xgid,
        "cubeValue": cube_value_number(cube.cube_value),
        "cubeOwner": "center" if cube.cube_value == 0 else ("onRoll" if cube.cube_value > 0 else "opponent"),
        "position": list(cube.position.points),
        "candidates": [
            {"rank": 1, "action": "Take", "equity": -cube.double_take_equity, **probability_fields(cube.double_take_analysis, invert=True)},
            {"rank": 2, "action": "Pass", "equity": -cube.double_drop_equity, **probability_fields(None)},
        ],
        **probability_fields(actual_eval, invert=True),
        "matchDate": match.header.date.date().isoformat() if match.header.date else None,
    }


def svg_text(text: str) -> str:
    return html.escape(str(text), quote=True)


def render_board_svg(row: dict[str, Any]) -> str:
    """Render a clean monochrome bgLog/Minstrels-inspired board diagram.

    The position is always viewed from the on-roll player's perspective:
    positive checkers are the on-roll side and are drawn in black; negative
    checkers are the opponent and are drawn in white.
    """
    width, height = 690, 546
    board_top, board_bottom = 28, 518
    top_label_y, bottom_label_y = 18, 540

    left_tray_x1, left_tray_x2 = 11, 59
    left_board_x1, left_board_x2 = 60, 327
    bar_x1, bar_x2 = 328, 367
    right_board_x1, right_board_x2 = 368, 637
    right_tray_x1, right_tray_x2 = 638, 684

    top_tip_y = 251
    bottom_tip_y = 294
    side_band_top, side_band_bottom = 247, 300
    point_w = (left_board_x2 - left_board_x1) / 6
    checker_r = 21.1

    points = row["position"]

    on_roll_pips = sum(point * max(int(points[point]), 0) for point in range(1, 25))
    on_roll_pips += 25 * max(int(points[25]), 0)
    opponent_pips = sum((25 - point) * max(-int(points[point]), 0) for point in range(1, 25))
    opponent_pips += 25 * max(-int(points[0]), 0)

    on_roll_on_board = sum(max(int(points[point]), 0) for point in range(1, 25)) + max(int(points[25]), 0)
    opponent_on_board = sum(max(-int(points[point]), 0) for point in range(1, 25)) + max(-int(points[0]), 0)
    on_roll_off = max(0, 15 - on_roll_on_board)
    opponent_off = max(0, 15 - opponent_on_board)

    elements: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Backgammon position {svg_text(row["id"])}">',
        '<rect width="690" height="546" fill="#ffffff"/>',
        '<g stroke="#000000" stroke-linejoin="round">',
        f'<rect x="{left_tray_x1}" y="{board_top}" width="{right_tray_x2-left_tray_x1}" height="{board_bottom-board_top}" fill="#ffffff" stroke-width="4"/>',
        f'<line x1="{left_tray_x2}" y1="{board_top}" x2="{left_tray_x2}" y2="{board_bottom}" stroke-width="4"/>',
        f'<line x1="{left_board_x2}" y1="{board_top}" x2="{left_board_x2}" y2="{board_bottom}" stroke-width="4"/>',
        f'<line x1="{bar_x2}" y1="{board_top}" x2="{bar_x2}" y2="{board_bottom}" stroke-width="4"/>',
        f'<line x1="{right_board_x2}" y1="{board_top}" x2="{right_board_x2}" y2="{board_bottom}" stroke-width="4"/>',
        f'<rect x="{left_tray_x1}" y="{side_band_top}" width="{left_tray_x2-left_tray_x1}" height="{side_band_bottom-side_band_top}" fill="#000000" stroke-width="0"/>',
        f'<rect x="{right_tray_x1}" y="{side_band_top}" width="{right_tray_x2-right_tray_x1}" height="{side_band_bottom-side_band_top}" fill="#000000" stroke-width="0"/>',
    ]

    def point_x(col: int, right_half: bool) -> float:
        origin = right_board_x1 if right_half else left_board_x1
        return origin + col * point_w

    # Top points: 13-18 on the left, 19-24 on the right.
    for half, origin_right in ((False, False), (True, True)):
        for col in range(6):
            x = point_x(col, origin_right)
            fill = "#cfcfcf" if col % 2 == 1 else "#ffffff"
            elements.append(
                f'<polygon points="{x:.2f},{board_top+2} {x+point_w:.2f},{board_top+2} '
                f'{x+point_w/2:.2f},{top_tip_y}" fill="{fill}" stroke-width="1"/>'
            )

    # Bottom points: 12-7 on the left, 6-1 on the right.
    for half, origin_right in ((False, False), (True, True)):
        for col in range(6):
            x = point_x(col, origin_right)
            fill = "#cfcfcf" if col % 2 == 0 else "#ffffff"
            elements.append(
                f'<polygon points="{x:.2f},{board_bottom-2} {x+point_w:.2f},{board_bottom-2} '
                f'{x+point_w/2:.2f},{bottom_tip_y}" fill="{fill}" stroke-width="1"/>'
            )

    elements.append('</g>')

    # Point labels, scores and pip counts.
    elements.extend([
        '<g fill="#000000" font-family="Arial, Helvetica, sans-serif" font-size="18">',
        f'<text x="20" y="{top_label_y}" text-anchor="middle">{row["onRollOpponentScore"]}/{row["matchLength"]}</text>',
        f'<text x="20" y="{bottom_label_y}" text-anchor="middle">{row["onRollScore"]}/{row["matchLength"]}</text>',
        f'<text x="347.5" y="{top_label_y}" text-anchor="middle">{opponent_pips}</text>',
        f'<text x="347.5" y="{bottom_label_y}" text-anchor="middle">{on_roll_pips}</text>',
    ])

    for col, point in enumerate(range(13, 19)):
        x = left_board_x1 + (col + 0.5) * point_w
        elements.append(f'<text x="{x:.2f}" y="{top_label_y}" text-anchor="middle">{point}</text>')
    for col, point in enumerate(range(19, 25)):
        x = right_board_x1 + (col + 0.5) * point_w
        elements.append(f'<text x="{x:.2f}" y="{top_label_y}" text-anchor="middle">{point}</text>')
    for col, point in enumerate(range(12, 6, -1)):
        x = left_board_x1 + (col + 0.5) * point_w
        elements.append(f'<text x="{x:.2f}" y="{bottom_label_y}" text-anchor="middle">{point}</text>')
    for col, point in enumerate(range(6, 0, -1)):
        x = right_board_x1 + (col + 0.5) * point_w
        elements.append(f'<text x="{x:.2f}" y="{bottom_label_y}" text-anchor="middle">{point}</text>')
    elements.append('</g>')

    def point_center(point: int) -> tuple[float, bool]:
        if 13 <= point <= 18:
            col = point - 13
            return left_board_x1 + (col + 0.5) * point_w, True
        if 19 <= point <= 24:
            col = point - 19
            return right_board_x1 + (col + 0.5) * point_w, True
        if 7 <= point <= 12:
            col = 12 - point
            return left_board_x1 + (col + 0.5) * point_w, False
        col = 6 - point
        return right_board_x1 + (col + 0.5) * point_w, False

    def checker(cx: float, cy: float, black: bool, count_label: int | None = None) -> None:
        fill = "#000000" if black else "#ffffff"
        text_fill = "#ffffff" if black else "#000000"
        elements.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{checker_r}" fill="{fill}" stroke="#000000" stroke-width="1.2"/>'
        )
        if count_label is not None:
            elements.append(
                f'<text x="{cx:.2f}" y="{cy+6:.2f}" text-anchor="middle" fill="{text_fill}" '
                f'font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="700">{count_label}</text>'
            )

    # Checkers on points. Positive/on-roll checkers are black; opponent checkers are white.
    for point in range(1, 25):
        value = int(points[point])
        if value == 0:
            continue
        count = abs(value)
        black = value > 0
        cx, top = point_center(point)
        visible = min(count, 5)
        step = 43.0
        for idx in range(visible):
            cy = board_top + 25 + idx * step if top else board_bottom - 25 - idx * step
            checker(cx, cy, black, count if idx == visible - 1 and count > 5 else None)

    # Bar checkers.
    bar_center = (bar_x1 + bar_x2) / 2
    opponent_bar = max(-int(points[0]), 0)
    on_roll_bar = max(int(points[25]), 0)
    for idx in range(min(opponent_bar, 5)):
        checker(bar_center, board_top + 25 + idx * 43, False, opponent_bar if idx == min(opponent_bar, 5) - 1 and opponent_bar > 5 else None)
    for idx in range(min(on_roll_bar, 5)):
        checker(bar_center, board_bottom - 25 - idx * 43, True, on_roll_bar if idx == min(on_roll_bar, 5) - 1 and on_roll_bar > 5 else None)

    # Doubling cube in the bar.
    cube_size = 36
    cube_x = bar_center - cube_size / 2
    if row["cubeOwner"] == "opponent":
        cube_y = board_top + 7
    elif row["cubeOwner"] == "onRoll":
        cube_y = board_bottom - cube_size - 7
    else:
        cube_y = (board_top + board_bottom - cube_size) / 2
    cube_label = "c" if row.get("isCrawford") else str(row["cubeValue"])
    elements.extend([
        f'<rect x="{cube_x:.2f}" y="{cube_y:.2f}" width="{cube_size}" height="{cube_size}" rx="3" fill="#ffffff" stroke="#000000" stroke-width="1.5"/>',
        f'<text x="{bar_center:.2f}" y="{cube_y+25:.2f}" text-anchor="middle" fill="#000000" font-family="Arial, Helvetica, sans-serif" font-size="22">{cube_label}</text>',
    ])

    # Dice, placed in the right half near the centre line.
    if row["diceValues"]:
        die_size = 36
        die_gap = 10
        start_x = 463
        die_y = 254
        pip_map = {
            1: [(18, 18)],
            2: [(10, 10), (26, 26)],
            3: [(10, 10), (18, 18), (26, 26)],
            4: [(10, 10), (26, 10), (10, 26), (26, 26)],
            5: [(10, 10), (26, 10), (18, 18), (10, 26), (26, 26)],
            6: [(10, 8), (26, 8), (10, 18), (26, 18), (10, 28), (26, 28)],
        }
        for idx, die in enumerate(row["diceValues"]):
            dx = start_x + idx * (die_size + die_gap)
            elements.append(f'<rect x="{dx}" y="{die_y}" width="{die_size}" height="{die_size}" rx="4" fill="#000000"/>')
            for px, py in pip_map[int(die)]:
                elements.append(f'<circle cx="{dx+px}" cy="{die_y+py}" r="3.4" fill="#ffffff"/>')

    # Borne-off checkers in the right tray.
    tray_center = (right_tray_x1 + right_tray_x2) / 2
    off_w, off_h = 41, 12
    for idx in range(opponent_off):
        y = board_top + 5 + idx * 13.8
        if y + off_h > side_band_top - 3:
            break
        elements.append(
            f'<rect x="{tray_center-off_w/2:.2f}" y="{y:.2f}" width="{off_w}" height="{off_h}" rx="4" fill="#ffffff" stroke="#000000" stroke-width="1"/>'
        )
    for idx in range(on_roll_off):
        y = board_bottom - 5 - off_h - idx * 13.8
        if y < side_band_bottom + 3:
            break
        elements.append(
            f'<rect x="{tray_center-off_w/2:.2f}" y="{y:.2f}" width="{off_w}" height="{off_h}" rx="4" fill="#000000" stroke="#000000" stroke-width="1"/>'
        )

    # On-roll marker (black side is always shown at the bottom).
    elements.append('<circle cx="660" cy="535" r="8.5" fill="#000000"/>')
    elements.append('</svg>')
    return "".join(elements)


def build() -> None:
    cfg = load_config()
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_DIR, DIST_DIR)
    BOARD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DIST_DIR / ".nojekyll").write_text("", encoding="utf-8")

    imported_files = sorted(
        [*IMPORTS_DIR.rglob("*.xg"), *IMPORTS_DIR.rglob("*.xgp")],
        key=lambda path: path.as_posix().casefold(),
    )
    rows: list[dict[str, Any]] = []
    match_summaries: list[dict[str, Any]] = []

    for source in imported_files:
        match = xgread.read(source)
        games_by_number = {game.header.game_number: game for game in match.games}
        before = len(rows)
        for decision in match.decisions():
            event = decision.event
            generated: list[dict[str, Any] | None]
            if isinstance(event, Move):
                generated = [make_checker_row(match, decision, event, cfg)]
            elif isinstance(event, CubeAction):
                generated = [
                    make_double_row(match, decision, event, cfg),
                    make_take_row(match, decision, event, cfg),
                ]
            else:
                generated = []

            for row in generated:
                if row is None:
                    continue
                game = games_by_number.get(decision.game_number)
                row["isCrawford"] = bool(game and game.header.crawford_apply)
                row["sourceFile"] = source.name
                if cfg["anonymizeOpponents"]:
                    row["opponent"] = "Opponent"
                    if row["onRollOpponent"] != row["player"]:
                        row["onRollOpponent"] = "Opponent"
                board_relative = f"assets/boards/{row['id']}.svg"
                row["boardImage"] = board_relative
                (DIST_DIR / board_relative).write_text(render_board_svg(row), encoding="utf-8")
                rows.append(row)

        match_summaries.append(
            {
                "sourceFile": source.name,
                "matchId": match.identity_hash,
                "player1": match.header.player1,
                "player2": match.header.player2,
                "matchLength": match.header.match_length,
                "positions": len(rows) - before,
            }
        )

    rows.sort(key=lambda row: (-float(row["errorLoss"]), row["sourceFile"], row["gameNumber"], row["moveNumber"]))
    payload = {
        "meta": {
            "title": cfg["databaseTitle"],
            "generatedAt": datetime.now(UTC).isoformat(),
            "errorThreshold": cfg["errorThreshold"],
            "blunderThreshold": cfg["blunderThreshold"],
            "targetPlayers": cfg["targetPlayers"],
            "themeColor": cfg["themeColor"],
            "sourceFileCount": len(imported_files),
            "positionCount": len(rows),
            "matches": match_summaries,
        },
        "positions": rows,
    }
    (DATA_DIR / "positions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Built {len(rows)} positions from {len(imported_files)} match file(s).")


if __name__ == "__main__":
    build()

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


def candidate_payload(move: Move) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, candidate in enumerate(move.candidates, start=1):
        rows.append(
            {
                "rank": rank,
                "action": xgread.format_moves(candidate.moves, move.position_before),
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
        xgread.format_moves(move.candidates[0].moves, move.position_before)
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
        "playedAction": move.notation,
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
    width, height = 760, 430
    bx, by = 25, 48
    point_w, bar_w, board_h = 40, 42, 330
    board_w = point_w * 12 + bar_w
    surface_x, surface_y = bx + 10, by + 10
    surface_w, surface_h = board_w - 20, board_h - 20
    bar_x = bx + 10 + point_w * 6
    tri_h = 142

    palette = {
        "frame": "#261C18",
        "frame2": "#513629",
        "surface": "#24423E",
        "bar": "#171F20",
        "pointA": "#D7B573",
        "pointB": "#8D3540",
        "light": "#F2E7CA",
        "lightStroke": "#A98F61",
        "dark": "#222832",
        "darkStroke": "#090B0E",
        "gold": "#C5A45E",
        "text": "#F7F1E4",
        "muted": "#BDB6A8",
    }

    elements: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Backgammon position {svg_text(row["id"])}">',
        "<defs>",
        '<filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity=".42"/></filter>',
        '<linearGradient id="wood" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#604235"/><stop offset=".5" stop-color="#34231E"/><stop offset="1" stop-color="#765242"/></linearGradient>',
        '<radialGradient id="lightChecker" cx="36%" cy="28%" r="72%"><stop offset="0" stop-color="#FFF9E9"/><stop offset=".72" stop-color="#E8D7B4"/><stop offset="1" stop-color="#BDA16B"/></radialGradient>',
        '<radialGradient id="darkChecker" cx="36%" cy="28%" r="72%"><stop offset="0" stop-color="#4B5362"/><stop offset=".68" stop-color="#222832"/><stop offset="1" stop-color="#090B0E"/></radialGradient>',
        "</defs>",
        f'<rect width="{width}" height="{height}" rx="18" fill="#111518"/>',
        f'<text x="25" y="28" fill="{palette["text"]}" font-family="Arial, sans-serif" font-size="15" font-weight="700">{svg_text(row["decisionLabel"])} · {svg_text(row["player"])} · {svg_text(row["classification"])}</text>',
        f'<rect x="{bx}" y="{by}" width="{board_w}" height="{board_h}" rx="12" fill="url(#wood)" stroke="#A68054" stroke-width="2"/>',
        f'<rect x="{surface_x}" y="{surface_y}" width="{surface_w}" height="{surface_h}" rx="4" fill="{palette["surface"]}" stroke="#111817" stroke-width="2"/>',
        f'<rect x="{bar_x}" y="{surface_y}" width="{bar_w}" height="{surface_h}" fill="{palette["bar"]}" opacity=".98"/>',
    ]

    top_points = list(range(13, 25))
    bottom_points = list(range(12, 0, -1))

    for col, point in enumerate(top_points):
        x = surface_x + col * point_w + (bar_w if col >= 6 else 0)
        color = palette["pointA"] if col % 2 == 0 else palette["pointB"]
        elements.append(
            f'<polygon points="{x},{surface_y} {x + point_w},{surface_y} {x + point_w / 2},{surface_y + tri_h}" fill="{color}" stroke="#2C2825" stroke-width="1"/>'
        )
        elements.append(f'<text x="{x + point_w / 2}" y="{surface_y + 15}" text-anchor="middle" fill="#221E1A" font-family="Arial" font-size="10" font-weight="700">{point}</text>')

    for col, point in enumerate(bottom_points):
        x = surface_x + col * point_w + (bar_w if col >= 6 else 0)
        color = palette["pointB"] if col % 2 == 0 else palette["pointA"]
        bottom = surface_y + surface_h
        elements.append(
            f'<polygon points="{x},{bottom} {x + point_w},{bottom} {x + point_w / 2},{bottom - tri_h}" fill="{color}" stroke="#2C2825" stroke-width="1"/>'
        )
        elements.append(f'<text x="{x + point_w / 2}" y="{bottom - 6}" text-anchor="middle" fill="#221E1A" font-family="Arial" font-size="10" font-weight="700">{point}</text>')

    def point_center(point: int) -> tuple[float, bool]:
        if point >= 13:
            col = point - 13
            top = True
        else:
            col = 12 - point
            top = False
        x = surface_x + col * point_w + (bar_w if col >= 6 else 0) + point_w / 2
        return x, top

    def checker(cx: float, cy: float, positive: bool, label: int | None = None) -> None:
        fill = "url(#lightChecker)" if positive else "url(#darkChecker)"
        stroke = palette["lightStroke"] if positive else palette["darkStroke"]
        text_color = "#201B14" if positive else "#FFFFFF"
        elements.append(f'<circle cx="{cx}" cy="{cy}" r="15.3" fill="{fill}" stroke="{stroke}" stroke-width="2" filter="url(#shadow)"/>')
        elements.append(f'<circle cx="{cx}" cy="{cy}" r="11.6" fill="none" stroke="{stroke}" stroke-opacity=".42"/>')
        if label is not None:
            elements.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="{text_color}" font-family="Arial" font-size="13" font-weight="900">{label}</text>')

    points = row["position"]
    for point in range(1, 25):
        value = int(points[point])
        if value == 0:
            continue
        count = abs(value)
        positive = value > 0
        cx, top = point_center(point)
        visible = min(count, 5)
        for idx in range(visible):
            cy = surface_y + 28 + idx * 28 if top else surface_y + surface_h - 28 - idx * 28
            checker(cx, cy, positive, count if idx == visible - 1 and count > 5 else None)

    # Bars: index 0 is opponent bar; index 25 is on-roll player's bar.
    bar_center = bar_x + bar_w / 2
    opp_bar = abs(int(points[0]))
    on_roll_bar = abs(int(points[25]))
    for idx in range(min(opp_bar, 5)):
        checker(bar_center, surface_y + 32 + idx * 29, False, opp_bar if idx == min(opp_bar, 5) - 1 and opp_bar > 5 else None)
    for idx in range(min(on_roll_bar, 5)):
        checker(bar_center, surface_y + surface_h - 32 - idx * 29, True, on_roll_bar if idx == min(on_roll_bar, 5) - 1 and on_roll_bar > 5 else None)

    panel_x = bx + board_w + 18
    panel_w = width - panel_x - 20
    elements.extend(
        [
            f'<rect x="{panel_x}" y="{by}" width="{panel_w}" height="{board_h}" rx="12" fill="#1B2226" stroke="#39444A"/>',
            f'<text x="{panel_x + 14}" y="{by + 27}" fill="{palette["gold"]}" font-family="Arial" font-size="12" font-weight="800">ON ROLL</text>',
            f'<text x="{panel_x + 14}" y="{by + 49}" fill="{palette["text"]}" font-family="Arial" font-size="15" font-weight="800">{svg_text(row["onRollPlayer"])}</text>',
            f'<text x="{panel_x + panel_w - 14}" y="{by + 49}" text-anchor="end" fill="{palette["text"]}" font-family="Arial" font-size="25" font-weight="900">{row["onRollScore"]}</text>',
            f'<line x1="{panel_x + 14}" x2="{panel_x + panel_w - 14}" y1="{by + 64}" y2="{by + 64}" stroke="#39444A"/>',
            f'<text x="{panel_x + 14}" y="{by + 88}" fill="{palette["muted"]}" font-family="Arial" font-size="12" font-weight="700">OPPONENT</text>',
            f'<text x="{panel_x + 14}" y="{by + 110}" fill="{palette["text"]}" font-family="Arial" font-size="15" font-weight="800">{svg_text(row["onRollOpponent"])}</text>',
            f'<text x="{panel_x + panel_w - 14}" y="{by + 110}" text-anchor="end" fill="{palette["text"]}" font-family="Arial" font-size="25" font-weight="900">{row["onRollOpponentScore"]}</text>',
            f'<text x="{panel_x + 14}" y="{by + 145}" fill="{palette["muted"]}" font-family="Arial" font-size="11">MATCH</text>',
            f'<text x="{panel_x + panel_w - 14}" y="{by + 145}" text-anchor="end" fill="{palette["text"]}" font-family="Arial" font-size="15" font-weight="800">{row["matchLength"]} pt</text>',
        ]
    )

    cube_y = by + 184
    cube_x = panel_x + 14 if row["cubeOwner"] != "opponent" else panel_x + panel_w - 54
    if row["cubeOwner"] == "center":
        cube_x = panel_x + (panel_w - 40) / 2
    elements.extend(
        [
            f'<rect x="{cube_x}" y="{cube_y}" width="40" height="40" rx="7" fill="#ECE5D4" stroke="#9D8D6D" stroke-width="2"/>',
            f'<text x="{cube_x + 20}" y="{cube_y + 27}" text-anchor="middle" fill="#1B1B1B" font-family="Arial" font-size="18" font-weight="900">{row["cubeValue"]}</text>',
        ]
    )

    if row["diceValues"]:
        for index, die in enumerate(row["diceValues"]):
            dx = panel_x + 20 + index * 58
            dy = by + 244
            elements.append(f'<rect x="{dx}" y="{dy}" width="45" height="45" rx="8" fill="#F4EAD2" stroke="#9D8D6D" stroke-width="2"/>')
            pip_positions = {
                1: [(22.5, 22.5)],
                2: [(12, 12), (33, 33)],
                3: [(12, 12), (22.5, 22.5), (33, 33)],
                4: [(12, 12), (33, 12), (12, 33), (33, 33)],
                5: [(12, 12), (33, 12), (22.5, 22.5), (12, 33), (33, 33)],
                6: [(12, 10), (33, 10), (12, 22.5), (33, 22.5), (12, 35), (33, 35)],
            }
            for px, py in pip_positions[int(die)]:
                elements.append(f'<circle cx="{dx + px}" cy="{dy + py}" r="3.7" fill="#26201B"/>')

    elements.extend(
        [
            f'<text x="{panel_x + 14}" y="{by + 314}" fill="{palette["muted"]}" font-family="Arial" font-size="10">Game {row["gameNumber"]} · Decision {row["moveNumber"]}</text>',
            f'<text x="25" y="413" fill="#9FA9AE" font-family="monospace" font-size="10">{svg_text(row["xgid"])}</text>',
            "</svg>",
        ]
    )
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

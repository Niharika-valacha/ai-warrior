"""The quiz state machine, owned by the server in multiplayer games.

A line-for-line port of web/lib/quiz.ts (which still runs solo games in the browser):

    ask ──right──▶ run ──▶ learn ──next──▶ ask (next level)
     │                ▲
     └─wrong─▶ fail ─retry─▶ retry ──right──┘
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal

Phase = Literal["ask", "fail", "retry", "run", "learn"]


@dataclass(frozen=True)
class QuizState:
    lvl: int = 0
    phase: Phase = "ask"
    picked: int = -1  # wrong option picked this level, -1 if none
    streak: int = 0  # right answers in a row on the first try

    def to_json(self) -> dict:
        return asdict(self)


def reduce(state: QuizState, action: dict, levels: list[dict]) -> QuizState:
    """Apply one action. Invalid actions return the state unchanged, so clients can't break the game."""
    kind = action.get("type")
    if kind == "pick":
        option = action.get("option")
        options = levels[state.lvl]["options"]
        right = isinstance(option, int) and 0 <= option < len(options) and options[option].get("correct") is True
        if state.phase == "ask":
            if right:
                return replace(state, phase="run", streak=state.streak + 1)
            if isinstance(option, int) and 0 <= option < len(options):
                return replace(state, phase="fail", picked=option, streak=0)
            return state
        if state.phase == "retry" and right:
            return replace(state, phase="run")
        return state
    if kind == "retry":
        return replace(state, phase="retry") if state.phase == "fail" else state
    if kind == "learn":
        return replace(state, phase="learn") if state.phase == "run" else state
    if kind == "next":
        if state.phase == "learn" and state.lvl < len(levels) - 1:
            return replace(state, lvl=state.lvl + 1, phase="ask", picked=-1)
        return state
    if kind == "reset":
        return QuizState()
    return state

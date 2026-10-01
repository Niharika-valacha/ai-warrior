// Pure quiz state machine. No React, no runtime imports, so it runs under `node --test`.
//
//   ask ──right──▶ run ──▶ learn ──next──▶ ask (next level)
//    │                ▲
//    └─wrong─▶ fail ─retry─▶ retry ──right──┘
export type Phase = "ask" | "fail" | "retry" | "run" | "learn";

export type QuizState = {
  lvl: number;
  phase: Phase;
  picked: number; // wrong option picked this level, -1 if none
  streak: number; // right answers in a row on the first try
};

export type QuizAction =
  | { type: "pick"; option: number }
  | { type: "retry" }
  | { type: "learn" }
  | { type: "next" }
  | { type: "reset" };

type Answerable = { options: { correct?: boolean }[] };

export const INITIAL_QUIZ: QuizState = { lvl: 0, phase: "ask", picked: -1, streak: 0 };

export function createQuizReducer(levels: Answerable[]) {
  return function quizReducer(state: QuizState, action: QuizAction): QuizState {
    switch (action.type) {
      case "pick": {
        const right = levels[state.lvl].options[action.option]?.correct === true;
        if (state.phase === "ask") {
          return right
            ? { ...state, phase: "run", streak: state.streak + 1 }
            : { ...state, phase: "fail", picked: action.option, streak: 0 };
        }
        if (state.phase === "retry" && right) return { ...state, phase: "run" };
        return state;
      }
      case "retry":
        return state.phase === "fail" ? { ...state, phase: "retry" } : state;
      case "learn":
        return state.phase === "run" ? { ...state, phase: "learn" } : state;
      case "next":
        return state.phase === "learn" && state.lvl < levels.length - 1
          ? { ...state, lvl: state.lvl + 1, phase: "ask", picked: -1 }
          : state;
      case "reset":
        return INITIAL_QUIZ;
    }
  };
}

/** How many blocks the system has, counting the one being added right now. */
export const builtCount = (s: QuizState) => s.lvl + (s.phase === "run" || s.phase === "learn" ? 1 : 0);

/** Lines for the terminal panel: the fail script on a wrong pick, the run log on a right one. */
export function terminalLines(level: { options: { fail?: string[] }[]; run: string[] }, s: QuizState): string[] {
  if (s.phase === "fail") return level.options[s.picked]?.fail ?? [];
  if (s.phase === "run" || s.phase === "learn") return level.run;
  return [];
}

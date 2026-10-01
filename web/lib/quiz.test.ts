import { test } from "node:test";
import assert from "node:assert/strict";
import { INITIAL_QUIZ, builtCount, createQuizReducer, terminalLines, type QuizState } from "./quiz.ts";

// Two levels: the right answer is B on level 0 and A on level 1.
const levels = [
  { options: [{ fail: ["boom"] }, { correct: true as const }], run: ["ok 0"] },
  { options: [{ correct: true as const }, { fail: ["boom"] }], run: ["ok 1"] },
];
const reduce = createQuizReducer(levels);
const play = (...actions: Parameters<typeof reduce>[1][]) => actions.reduce(reduce, INITIAL_QUIZ);

test("a wrong pick fails, and retry only accepts the right answer", () => {
  let s: QuizState = play({ type: "pick", option: 0 });
  assert.deepEqual(s, { lvl: 0, phase: "fail", picked: 0, streak: 0 });
  assert.deepEqual(terminalLines(levels[0], s), ["boom"]);

  s = reduce(s, { type: "retry" });
  assert.equal(s.phase, "retry");
  assert.equal(reduce(s, { type: "pick", option: 0 }), s, "wrong option is ignored on retry");

  s = reduce(s, { type: "pick", option: 1 });
  assert.equal(s.phase, "run");
  assert.equal(s.streak, 0, "a retry never counts as a first try");
});

test("first-try answers build the streak and the system", () => {
  let s = play({ type: "pick", option: 1 });
  assert.equal(builtCount(s), 1);
  s = play({ type: "pick", option: 1 }, { type: "learn" }, { type: "next" }, { type: "pick", option: 0 });
  assert.deepEqual(s, { lvl: 1, phase: "run", picked: -1, streak: 2 });
  assert.equal(builtCount(s), 2);
});

test("next is a no-op on the last level and before learn", () => {
  assert.equal(play({ type: "next" }).lvl, 0);
  const last = play({ type: "pick", option: 1 }, { type: "learn" }, { type: "next" }, { type: "pick", option: 0 }, { type: "learn" });
  assert.equal(reduce(last, { type: "next" }), last);
});

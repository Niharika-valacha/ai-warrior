"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { useContent } from "./ContentProvider";
import { INITIAL_QUIZ, createQuizReducer, type QuizAction, type QuizState } from "@/lib/quiz";
import { allSidekickImages } from "@/lib/sidekicks";
import { BossScreen } from "./screens/BossScreen";
import { BriefingScreen } from "./screens/BriefingScreen";
import { IntroScreen } from "./screens/IntroScreen";
import { LevelScreen } from "./screens/LevelScreen";
import { MemeScreen } from "./screens/MemeScreen";
import { NameScreen } from "./screens/NameScreen";
import { SidekickScreen } from "./screens/SidekickScreen";
import { SkillTreeScreen } from "./screens/SkillTreeScreen";
import { WinScreen } from "./screens/WinScreen";

export type Screen = "intro" | "name" | "sidekick" | "briefing" | "level" | "boss" | "meme" | "tree" | "win";

type Props = {
  /** Multiplayer: the server owns the quiz and this sends it actions. Solo games keep the quiz in the browser. */
  remote?: { quiz: QuizState; dispatch: (action: QuizAction) => void };
  /** Where to begin; a multiplayer host goes straight to the briefing. */
  startAt?: Screen;
  initialName?: string;
};

/** Screen flow: intro → name → sidekick → briefing → 11 levels → boss → meme → skill tree → win. */
export default function Game({ remote, startAt = "intro", initialName = "" }: Props) {
  const { levels, sidekicks } = useContent();
  const quizReducer = useMemo(() => createQuizReducer(levels), [levels]);
  const [screen, setScreen] = useState<Screen>(startAt);
  const [name, setName] = useState(initialName);
  const [sidekickId, setSidekickId] = useState(sidekicks[0].id);
  const [localQuiz, localDispatch] = useReducer(quizReducer, INITIAL_QUIZ);
  const quiz = remote?.quiz ?? localQuiz;
  const dispatch = remote?.dispatch ?? localDispatch;
  const sidekick = sidekicks.find((s) => s.id === sidekickId) ?? sidekicks[0];

  // Preload every expression so mood swaps don't flicker on stage.
  useEffect(() => {
    allSidekickImages(sidekicks).forEach((src) => (new Image().src = src));
  }, [sidekicks]);

  switch (screen) {
    case "intro":
      return <IntroScreen onStart={() => setScreen("name")} />;
    case "name":
      return <NameScreen name={name} onChange={setName} onSubmit={() => setScreen("sidekick")} />;
    case "sidekick":
      return (
        <SidekickScreen
          onPick={(id) => {
            setSidekickId(id);
            setScreen("briefing");
          }}
        />
      );
    case "briefing":
      return <BriefingScreen name={name} sidekick={sidekick} onStart={() => setScreen("level")} />;
    case "level":
      return (
        <LevelScreen quiz={quiz} dispatch={dispatch} name={name} sidekick={sidekick} onComplete={() => setScreen("boss")} />
      );
    case "boss":
      return <BossScreen onAnswer={() => setScreen("meme")} />;
    case "meme":
      return <MemeScreen onFinish={() => setScreen("tree")} />;
    case "tree":
      return <SkillTreeScreen onFinish={() => setScreen("win")} />;
    case "win":
      return (
        <WinScreen
          name={name}
          sidekick={sidekick}
          onRestart={() => {
            dispatch({ type: "reset" });
            setScreen(startAt);
          }}
        />
      );
  }
}

"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { useContent } from "./ContentProvider";
import { INITIAL_QUIZ, createQuizReducer } from "@/lib/quiz";
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

type Screen = "intro" | "name" | "sidekick" | "briefing" | "level" | "boss" | "meme" | "tree" | "win";

/** Screen flow: intro → name → sidekick → briefing → 11 levels → boss → meme → skill tree → win. */
export default function Game() {
  const { levels, sidekicks } = useContent();
  const quizReducer = useMemo(() => createQuizReducer(levels), [levels]);
  const [screen, setScreen] = useState<Screen>("intro");
  const [name, setName] = useState("");
  const [sidekickId, setSidekickId] = useState(sidekicks[0].id);
  const [quiz, dispatch] = useReducer(quizReducer, INITIAL_QUIZ);
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
            setScreen("intro");
          }}
        />
      );
  }
}

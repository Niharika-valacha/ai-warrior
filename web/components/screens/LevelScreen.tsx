import { useState, type Dispatch } from "react";
import { useContent } from "@/components/ContentProvider";
import { builtCount, terminalLines, type QuizAction, type QuizState } from "@/lib/quiz";
import { reaction } from "@/lib/sidekicks";
import type { Sidekick } from "@/lib/types";
import { useHotkeys } from "@/lib/useHotkeys";
import { useReveal } from "@/lib/useReveal";
import { IncidentTag } from "@/components/IncidentTag";
import { ConceptCard } from "@/components/level/ConceptCard";
import { OptionList } from "@/components/level/OptionList";
import { RunTerminal } from "@/components/level/RunTerminal";
import { SideQuestPanel } from "@/components/level/SideQuestPanel";
import { XrayPanel } from "@/components/level/XrayPanel";
import { GameLayout } from "@/components/shell/GameLayout";

type Props = {
  quiz: QuizState;
  dispatch: Dispatch<QuizAction>;
  name: string;
  sidekick: Sidekick;
  onComplete: () => void;
};

export function LevelScreen({ quiz, dispatch, name, sidekick, onComplete }: Props) {
  const { levels, copy } = useContent();
  const { lvl, phase, picked } = quiz;
  const level = levels[lvl];
  const isLast = lvl === levels.length - 1;
  const choosing = phase === "ask" || phase === "retry";
  const solved = phase === "run" || phase === "learn";
  // Remember which level X-ray was opened for, so it closes itself on the next level.
  const [xrayLevel, setXrayLevel] = useState<number | null>(null);
  const xrayOpen = xrayLevel === lvl;
  const [questLevel, setQuestLevel] = useState<number | null>(null);
  const questOpen = questLevel === lvl;
  const lines = terminalLines(level, quiz);
  // "run" and "learn" share one log, so moving to learn must not restart it.
  const reveal = useReveal(lines, `${lvl}-${phase === "learn" ? "run" : phase}-${picked}`);

  const primary: { label: string; action: () => void } | null =
    !reveal.done && (phase === "fail" || phase === "run")
      ? { label: "Skip", action: reveal.skip }
      : phase === "fail"
        ? { label: "Try again", action: () => dispatch({ type: "retry" }) }
        : phase === "run"
          ? { label: "What just happened?", action: () => dispatch({ type: "learn" }) }
          : phase === "learn"
            ? { label: isLast ? "Finish" : "Next level", action: isLast ? onComplete : () => dispatch({ type: "next" }) }
            : null;

  useHotkeys((key) => {
    if (key === "x" && solved && !questOpen) {
      setXrayLevel(xrayOpen ? null : lvl);
      return true;
    }
    if (key === "q" && phase === "learn" && !xrayOpen) {
      setQuestLevel(questOpen ? null : lvl);
      return true;
    }
    if (xrayOpen || questOpen) return false; // an open panel owns the keyboard
    if (choosing && ["1", "2", "3", "4"].includes(key)) {
      dispatch({ type: "pick", option: Number(key) - 1 });
      return true;
    }
    if ((key === "enter" || key === "n") && primary) {
      primary.action();
      return true;
    }
    if (key === "s") {
      reveal.skip();
      return true;
    }
    return false;
  });

  const { mood, line } = reaction(sidekick, phase, copy.reactions);
  const wrong = picked >= 0 ? level.options[picked] : undefined;

  return (
    <GameLayout
      name={name}
      status={`Level ${lvl} of ${levels.length - 1}`}
      streak={quiz.streak}
      pipeline={{
        built: builtCount(quiz),
        fresh: phase === "run" || phase === "learn",
        failed: phase === "fail" ? wrong?.text : undefined,
        slot: choosing,
      }}
      sidekick={sidekick}
      mood={mood}
      line={line}
    >
      {phase !== "learn" && (
        <div className="incident">
          <IncidentTag id={4100 + lvl * 37} alert={level.alert} />
          {level.situation.map((s) => (
            <p key={s}>{s}</p>
          ))}
        </div>
      )}

      <h2 className="question">{level.question}</h2>

      {choosing ? (
        <OptionList
          options={level.options}
          onlyCorrect={phase === "retry"}
          onPick={(i) => dispatch({ type: "pick", option: i })}
        />
      ) : (
        <RunTerminal
          failed={phase === "fail"}
          status={
            phase === "fail"
              ? `✕ ${wrong?.text}`
              : `✓ Correct${picked < 0 ? ", first try" : ""}. ${level.block} added to your system.`
          }
          lines={lines.slice(0, reveal.shown)}
        />
      )}

      {phase === "fail" && reveal.done && <p className="pun">{wrong?.pun}</p>}

      {phase === "learn" && <ConceptCard learn={level.learn} concept={level.concept} />}

      {primary && (
        <div className="actions">
          <button className="btn" onClick={primary.action}>
            {primary.label}
          </button>
          <span className="hint">Enter</span>
          {solved && (
            <>
              <button className="btn-ghost" onClick={() => setXrayLevel(lvl)}>
                X-ray the code
              </button>
              <span className="hint">X</span>
            </>
          )}
          {phase === "learn" && (
            <>
              <button className="btn-ghost" onClick={() => setQuestLevel(lvl)}>
                {copy.sidequest.button}
              </button>
              <span className="hint">Q</span>
            </>
          )}
        </div>
      )}

      {xrayOpen && <XrayPanel level={lvl} onClose={() => setXrayLevel(null)} />}
      {questOpen && <SideQuestPanel level={level} onClose={() => setQuestLevel(null)} />}
    </GameLayout>
  );
}

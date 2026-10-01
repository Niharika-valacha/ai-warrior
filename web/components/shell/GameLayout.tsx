import type { ReactNode } from "react";
import { useContent } from "@/components/ContentProvider";
import type { Mood } from "@/lib/sidekicks";
import type { Sidekick } from "@/lib/types";
import { Buddy } from "./Buddy";
import { SystemPipeline, type PipelineProps } from "./SystemPipeline";

type Props = {
  name: string;
  status: string;
  streak?: number;
  pipeline: PipelineProps;
  sidekick: Sidekick;
  mood: Mood;
  line: string;
  bigBuddy?: boolean;
  children: ReactNode;
};

/** Top bar + main column + the right-hand side (system pipeline and sidekick). */
export function GameLayout({ name, status, streak = 0, pipeline, sidekick, mood, line, bigBuddy, children }: Props) {
  const { levels } = useContent();
  return (
    <div className="app">
      <header className="topbar">
        <span className="wordmark">AI Warrior</span>
        <span className="meta">
          {name} · {status}
          {streak > 1 && <span className="streak"> · {streak} first tries in a row</span>}
        </span>
        <div
          className="progress"
          role="progressbar"
          aria-valuenow={pipeline.built}
          aria-valuemin={0}
          aria-valuemax={levels.length}
        >
          {levels.map((l, i) => (
            <span key={l.block} className={i < pipeline.built ? "on" : ""} />
          ))}
        </div>
      </header>

      <main className="game">
        <section className="play">{children}</section>
        <aside className="side">
          <SystemPipeline {...pipeline} />
          <Buddy sidekick={sidekick} mood={mood} line={line} size={bigBuddy ? 200 : 136} />
        </aside>
      </main>
    </div>
  );
}

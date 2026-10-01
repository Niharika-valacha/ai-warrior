import { Avatar } from "@/components/Avatar";
import { useContent } from "@/components/ContentProvider";
import { IncidentTag } from "@/components/IncidentTag";
import { Rich, fill } from "@/lib/text";
import type { Sidekick } from "@/lib/types";

type Props = { name: string; sidekick: Sidekick; onStart: () => void };

/** The problem statement and rules, shown once before Level 0. */
export function BriefingScreen({ name, sidekick, onStart }: Props) {
  const { levels, copy } = useContent();
  const brief = copy.briefing;
  const vars = { name, levels: levels.length };

  return (
    <main className="brief">
      <header className="brief-head">
        <span className="chip">Mission briefing</span>
        <h1>{brief.title}</h1>
      </header>

      <section className="brief-problem" aria-label="The problem">
        <IncidentTag id={brief.incidentId} alert={brief.alert} />
        <p>
          <Rich text={brief.problem} />
        </p>
        <ul className="quotes">
          {brief.quotes.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
        <p>
          <Rich text={brief.job} />
        </p>
      </section>

      <section className="brief-cols">
        <div>
          <h2>How it works</h2>
          <ul className="rules">
            {brief.rules.map((r) => (
              <li key={r}>
                <Rich text={fill(r, vars)} />
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2>What you&apos;ll build</h2>
          <ol className="roadmap">
            {levels.map((l) => (
              <li key={l.block}>{l.block}</li>
            ))}
          </ol>
        </div>
      </section>

      <footer className="brief-foot">
        <button className="btn" onClick={onStart} autoFocus>
          {brief.start}
        </button>
        <div className="brief-buddy">
          <Avatar sidekick={sidekick} mood="win" size={88} />
          <span>
            {sidekick.name}: “{sidekick.move}”
          </span>
        </div>
      </footer>
    </main>
  );
}

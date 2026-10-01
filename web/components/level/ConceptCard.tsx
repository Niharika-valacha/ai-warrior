import type { Level } from "@/lib/types";

/** The learn note plus the "Concept unlocked" card shown after a right answer. */
export function ConceptCard({ learn, concept }: Pick<Level, "learn" | "concept">) {
  return (
    <div className="learn">
      <p className="learn-note">{learn}</p>
      <article className="concept">
        <header>
          <span className="chip">Concept unlocked</span>
          <h3>{concept.name}</h3>
          <p className="concept-term">{concept.term}</p>
        </header>
        <dl>
          <dt>How it works</dt>
          <dd>{concept.parts}</dd>
          <dt>The AI twist</dt>
          <dd>{concept.twist}</dd>
        </dl>
        <p className="concept-line">{concept.line}</p>
      </article>
    </div>
  );
}

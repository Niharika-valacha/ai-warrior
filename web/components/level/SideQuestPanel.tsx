import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useContent } from "@/components/ContentProvider";
import { askFollowUp, loadSideQuest, refreshSideQuest, type FollowUp, type SideQuestRecord, type Source } from "@/lib/sidequest";
import type { Level } from "@/lib/types";
import { useHotkeys } from "@/lib/useHotkeys";

const CHAPTERS = ["The story", "Before & after", "In production", "For your role", "Tools to try", "At scale"];

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; record: SideQuestRecord; offline: boolean };

/** Turn "[3]" in generated text into links to the cited source. */
function Cited({ text, sources }: { text: string; sources: Source[] }) {
  return (
    <>
      {text.split(/(\[\d+\])/g).map((part, i) => {
        const n = /^\[(\d+)\]$/.exec(part)?.[1];
        const src = n ? sources.find((s) => s.n === Number(n)) : undefined;
        return src ? (
          <a key={i} className="cite" href={src.url} target="_blank" rel="noreferrer" title={src.title}>
            {n}
          </a>
        ) : (
          part
        );
      })}
    </>
  );
}

/** The deep-dive pop-up for one level: six researched chapters plus live follow-up questions. */
export function SideQuestPanel({ level, onClose }: { level: Level; onClose: () => void }) {
  const copy = useContent().copy.sidequest;
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [chapter, setChapter] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState("");
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [showFollowUps, setShowFollowUps] = useState(false);

  useEffect(() => {
    let alive = true;
    loadSideQuest(level.id)
      .then(({ record, offline }) => alive && setLoad({ status: "ready", record, offline }))
      .catch((err: Error) => alive && setLoad({ status: "error", message: err.message }));
    return () => {
      alive = false;
    };
  }, [level.id]);

  const go = (i: number) => {
    setShowFollowUps(false);
    setChapter((i + CHAPTERS.length) % CHAPTERS.length);
  };

  useHotkeys((key) => {
    if (key === "escape") onClose();
    else if (/^[1-6]$/.test(key)) go(Number(key) - 1);
    else if (key === "arrowright") go(chapter + 1);
    else if (key === "arrowleft") go(chapter - 1);
    else return false;
    return true;
  });

  async function refresh() {
    setRefreshing(true);
    setNotice("");
    try {
      const record = await refreshSideQuest(level.id);
      setLoad({ status: "ready", record, offline: false });
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="xray-backdrop" role="dialog" aria-modal="true" aria-labelledby="sq-title">
      <section className="sq">
        <header className="sq-head">
          <div className="sq-tags">
            <span className="sq-tag sq-tag-quest">Side quest</span>
            <span className="sq-tag">Level {level.id}</span>
            {load.status === "ready" && (
              <span className={`sq-tag ${load.offline ? "sq-tag-offline" : ""}`}>
                {load.offline ? "Saved copy" : "Researched"} · {load.record.sources.length} sources · {load.record.model}
              </span>
            )}
          </div>
          <h2 id="sq-title">{level.concept.name}</h2>
          <p className="sq-oneliner">{load.status === "ready" ? load.record.quest.oneLiner : level.concept.term}</p>
        </header>

        <nav className="sq-tabs" role="tablist" aria-label="Side quest chapters">
          {CHAPTERS.map((name, i) => (
            <button
              key={name}
              role="tab"
              className="sq-tab"
              aria-selected={!showFollowUps && i === chapter}
              onClick={() => go(i)}
            >
              <kbd>{i + 1}</kbd>
              {name}
            </button>
          ))}
          {followUps.length > 0 && (
            <button role="tab" className="sq-tab" aria-selected={showFollowUps} onClick={() => setShowFollowUps(true)}>
              Follow-ups ({followUps.length})
            </button>
          )}
        </nav>

        <div className="sq-panel" role="tabpanel">
          {load.status === "loading" && <p className="sq-status">{copy.loading}</p>}
          {load.status === "error" && (
            <p className="sq-status sq-error">This side quest couldn&apos;t be generated: {load.message}</p>
          )}
          {load.status === "ready" &&
            (showFollowUps ? (
              <FollowUps items={followUps} />
            ) : (
              <Chapter index={chapter} record={load.record} builtWith={copy} />
            ))}
        </div>

        <AskBox
          levelId={level.id}
          placeholder={copy.askPlaceholder}
          disabled={load.status !== "ready" || load.offline}
          onAnswer={(f) => {
            setFollowUps((list) => [f, ...list]);
            setShowFollowUps(true);
          }}
        />

        <footer className="sq-foot">
          <button className="btn-ghost" onClick={() => go(chapter - 1)}>
            Previous <kbd>←</kbd>
          </button>
          <button className="btn" onClick={() => go(chapter + 1)} autoFocus>
            Next chapter <kbd>→</kbd>
          </button>
          <span className="spacer" />
          {notice && <span className="sq-notice">{notice}</span>}
          <button className="btn-ghost" onClick={refresh} disabled={refreshing || load.status !== "ready" || load.offline}>
            {refreshing ? "Researching again…" : "Refresh"}
          </button>
          <button className="btn-ghost" onClick={onClose}>
            Back to the game <kbd>Esc</kbd>
          </button>
        </footer>
      </section>
    </div>
  );
}

function Chapter({ index, record, builtWith }: { index: number; record: SideQuestRecord; builtWith: { builtWithTitle: string; builtWith: { name: string; what: string }[] } }) {
  const { quest: q, sources } = record;
  const cite = (text: string) => <Cited text={text} sources={sources} />;

  const chapters: ReactNode[] = [
    <div key="story">
      <div className="sq-story">
        <div className="sq-beat sq-pain">
          <h3>The pain</h3>
          <p>{cite(q.story.pain)}</p>
        </div>
        <div className="sq-beat">
          <h3>The idea</h3>
          <p>{cite(q.story.idea)}</p>
        </div>
        <div className="sq-beat sq-aha">
          <h3>What it unlocked</h3>
          <p>{cite(q.story.unlocked)}</p>
        </div>
      </div>
      <p className="sq-origin">{cite(q.story.origin)}</p>
      <details className="sq-sources">
        <summary>All {sources.length} sources</summary>
        <ol>
          {sources.map((s) => (
            <li key={s.n} value={s.n}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title || s.url}
              </a>
            </li>
          ))}
        </ol>
      </details>
    </div>,

    <div key="before" className="table-wrap">
      <table className="sq-compare">
        <thead>
          <tr>
            <th>Approach</th>
            <th>How it works</th>
            <th>Where it breaks</th>
          </tr>
        </thead>
        <tbody>
          {q.beforeAfter.map((row, i) => (
            <tr key={row.approach} className={i === q.beforeAfter.length - 1 ? "sq-win" : ""}>
              <td>{row.approach}</td>
              <td>{cite(row.how)}</td>
              <td>{cite(row.breaks)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>,

    <div key="prod" className="sq-cards">
      {q.production.map((p) => (
        <div key={p.title} className="sq-card">
          <h3>{p.title}</h3>
          <p>{cite(p.text)}</p>
        </div>
      ))}
    </div>,

    <div key="roles" className="sq-cards">
      {(
        [
          ["🧪 QA", q.roles.qa],
          ["🎨 Frontend", q.roles.frontend],
          ["⚙️ Backend", q.roles.backend],
          ["📈 Leadership", q.roles.leadership],
        ] as const
      ).map(([role, points]) => (
        <div key={role} className={`sq-role ${role.includes("Leadership") ? "sq-role-lead" : ""}`}>
          <h3>{role}</h3>
          <ul>
            {points.map((pt) => (
              <li key={pt}>{cite(pt)}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>,

    <div key="tools" className="sq-cards">
      {q.tools.map((g) => (
        <div key={g.group} className="sq-card">
          <h3 className="sq-group">{g.group}</h3>
          {g.items.map((t) => (
            <p key={t.name}>
              <b>{t.name}</b>
              <br />
              {cite(t.what)}
            </p>
          ))}
        </div>
      ))}
      <div className="sq-card sq-mine">
        <h3 className="sq-group">{builtWith.builtWithTitle}</h3>
        {builtWith.builtWith.map((t) => (
          <p key={t.name}>
            <b>{t.name}</b>
            <br />
            {t.what}
          </p>
        ))}
      </div>
    </div>,

    <div key="scale" className="sq-scale">
      <div>
        <p className="sq-lead">{cite(q.atScale.lead)}</p>
        <div className="sq-ops">
          {q.atScale.ops.map((op) => (
            <div key={op.name} className="sq-op">
              <b>{op.name}</b>
              <span>{cite(op.text)}</span>
            </div>
          ))}
        </div>
      </div>
      <aside className="sq-flex" aria-label="Why this is engineering">
        <p className="sq-big">The model is about {q.atScale.modelShare}% of it.</p>
        <div className="sq-meter" aria-hidden="true">
          <div style={{ width: `${q.atScale.modelShare}%` }}>model</div>
          <div>engineering</div>
        </div>
        <p>{cite(q.atScale.takeaway)}</p>
      </aside>
    </div>,
  ];

  return chapters[index];
}

function FollowUps({ items }: { items: FollowUp[] }) {
  return (
    <div className="sq-followups">
      {items.map((f, i) => (
        <article key={i} className="sq-answer">
          <h3>{f.question}</h3>
          <p>
            <Cited text={f.answer} sources={f.sources} />
          </p>
          <ol className="sq-answer-sources">
            {f.sources.map((s) => (
              <li key={s.n} value={s.n}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.title || s.url}
                </a>
              </li>
            ))}
          </ol>
        </article>
      ))}
    </div>
  );
}

function AskBox({ levelId, placeholder, disabled, onAnswer }: { levelId: number; placeholder: string; disabled: boolean; onAnswer: (f: FollowUp) => void }) {
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (question.trim().length < 3 || asking) return;
    setAsking(true);
    setError("");
    try {
      onAnswer(await askFollowUp(levelId, question.trim()));
      setQuestion("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAsking(false);
    }
  }

  return (
    <form className="sq-ask" onSubmit={submit}>
      <label htmlFor="sq-question" className="sr-only">
        Ask a follow-up question
      </label>
      <input
        id="sq-question"
        value={question}
        maxLength={300}
        placeholder={disabled ? "Follow-ups need the API and its keys" : placeholder}
        disabled={disabled || asking}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && (e.currentTarget.blur(), e.stopPropagation())}
      />
      <button className="btn" type="submit" disabled={disabled || asking || question.trim().length < 3}>
        {asking ? "Searching the web…" : "Ask live"}
      </button>
      {error && <p className="sq-error">{error}</p>}
    </form>
  );
}

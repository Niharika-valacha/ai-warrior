import type { CSSProperties } from "react";
import { useContent } from "@/components/ContentProvider";
import { fill } from "@/lib/text";

const STAGGER_MS = 45;

/** Season 1 recap: today's topics light up one by one; the rest are locked for next time. */
export function SkillTreeScreen({ onFinish }: { onFinish: () => void }) {
  const { skillTree, copy } = useContent();
  const unlockedCount = skillTree.reduce((n, b) => n + b.unlocked.length, 0);
  const lockedCount = skillTree.reduce((n, b) => n + b.locked.length, 0);
  let order = 0; // global reveal order across branches, so topics light up left to right

  return (
    <main className="tree">
      <header className="tree-head">
        <span className="chip">Season 1 complete</span>
        <h1>{copy.tree.title}</h1>
        <p className="lede">{fill(copy.tree.lede, { unlocked: unlockedCount, locked: lockedCount })}</p>
      </header>

      <div className="tree-branches">
        {skillTree.map((branch) => (
          <section key={branch.name} className="branch" aria-label={branch.name}>
            <h2>
              {branch.name}
              <span className="branch-count">
                {branch.unlocked.length}/{branch.unlocked.length + branch.locked.length}
              </span>
            </h2>
            <ul>
              {branch.unlocked.map((t) => (
                <li key={t} className="topic topic-on" style={{ "--delay": `${order++ * STAGGER_MS}ms` } as CSSProperties}>
                  {t}
                </li>
              ))}
              {branch.locked.map((t) => (
                <li key={t} className="topic topic-locked">
                  <span className="sr-only">Locked: </span>
                  {t}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <footer className="tree-foot">
        <p>{copy.tree.footer}</p>
        <button className="btn" onClick={onFinish} autoFocus>
          Finish
        </button>
      </footer>
    </main>
  );
}

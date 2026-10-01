import { useContent } from "@/components/ContentProvider";
import { GameLayout } from "@/components/shell/GameLayout";
import { fill } from "@/lib/text";
import type { Sidekick } from "@/lib/types";

type Props = { name: string; sidekick: Sidekick; onRestart: () => void };

export function WinScreen({ name, sidekick, onRestart }: Props) {
  const { levels, copy } = useContent();
  const vars = { name, levels: levels.length };
  return (
    <GameLayout
      name={name}
      status="Complete"
      pipeline={{ built: levels.length }}
      sidekick={sidekick}
      mood="win"
      line={copy.reactions.shipped}
      bigBuddy
    >
      <h1 className="win-title">{fill(copy.win.title, vars)}</h1>
      <p className="lede">{fill(copy.win.lede, vars)}</p>
      <div>
        <button className="btn" onClick={onRestart} autoFocus>
          {copy.win.again}
        </button>
      </div>
    </GameLayout>
  );
}

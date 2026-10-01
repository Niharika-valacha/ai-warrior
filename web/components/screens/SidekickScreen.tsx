import { Avatar } from "@/components/Avatar";
import { useContent } from "@/components/ContentProvider";

export function SidekickScreen({ onPick }: { onPick: (id: string) => void }) {
  const { sidekicks } = useContent();
  return (
    <main className="intro">
      <h1 className="intro-label">Choose your sidekick</h1>
      <div className="fighters">
        {sidekicks.map((s) => (
          <button key={s.id} className="fighter" onClick={() => onPick(s.id)}>
            <Avatar sidekick={s} size={200} />
            <span className="fighter-name">{s.name}</span>
            <span className="fighter-role">{s.role}</span>
            <span className="fighter-move">“{s.move}”</span>
          </button>
        ))}
      </div>
    </main>
  );
}

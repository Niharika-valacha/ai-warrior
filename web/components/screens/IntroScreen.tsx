import Link from "next/link";
import { Avatar } from "@/components/Avatar";
import { useContent } from "@/components/ContentProvider";
import { fill } from "@/lib/text";

export function IntroScreen({ onStart }: { onStart: () => void }) {
  const { levels, sidekicks, copy } = useContent();
  const [first, second] = sidekicks;
  return (
    <main className="intro">
      <div className="intro-cast">
        {first && <Avatar sidekick={first} mood="idle" size={180} />}
        {second && <Avatar sidekick={second} mood="win" size={180} />}
      </div>
      <h1>{copy.intro.title}</h1>
      <p className="lede">{fill(copy.intro.lede, { levels: levels.length })}</p>
      <button className="btn" onClick={onStart} autoFocus>
        {copy.intro.start}
      </button>
      <Link className="intro-host" href="/host">
        Host a multiplayer game, everyone plays from their phone
      </Link>
    </main>
  );
}

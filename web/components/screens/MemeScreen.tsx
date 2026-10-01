import { useState } from "react";

const MEME_SRC = "/meme.jpg";

export function MemeScreen({ onFinish }: { onFinish: () => void }) {
  const [missing, setMissing] = useState(false);

  return (
    <main className="intro">
      {missing ? (
        <div className="meme-slot">Meme goes here: save it as web/public{MEME_SRC}</div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="meme" src={MEME_SRC} alt="The meme" onError={() => setMissing(true)} />
      )}
      <button className="btn" onClick={onFinish} autoFocus>
        Finish
      </button>
    </main>
  );
}

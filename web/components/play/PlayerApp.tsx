"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useContent } from "@/components/ContentProvider";
import { clearSeat, joinRoom, loadSeat, saveSeat, useRoom, type RoomState, type Seat } from "@/lib/room";

const TEAMS = ["QA", "Frontend", "Backend", "Leadership"];
const KEYS = ["A", "B", "C", "D"];

/** The phone in a multiplayer game: join a room, then follow along live. */
export function PlayerApp({ initialCode }: { initialCode: string }) {
  const [seat, setSeat] = useState<Seat | null>(null);
  const [notice, setNotice] = useState("");
  const { room, connection } = useRoom(seat);

  // Coming back to the same room (refresh, locked screen, crashed tab) reuses your seat.
  useEffect(() => {
    const saved = loadSeat("player");
    if (saved && (!initialCode || saved.code === initialCode.toUpperCase())) setSeat(saved);
  }, [initialCode]);

  // The room is gone (game over long ago, or the API restarted): back to the join form.
  useEffect(() => {
    if (connection === "refused") {
      clearSeat("player");
      setSeat(null);
      setNotice("That room has closed. Ask the host for a new code.");
    }
  }, [connection]);

  if (!seat) {
    return (
      <JoinForm
        initialCode={initialCode}
        notice={notice}
        onJoined={(next) => {
          saveSeat("player", next);
          setNotice("");
          setSeat(next);
        }}
      />
    );
  }

  return (
    <main className="phone">
      {connection === "reconnecting" && <p className="phone-reconnect">Reconnecting…</p>}
      <header className="phone-head">
        <span className="phone-me">{seat.name}</span>
        <span className="phone-team">{seat.team}</span>
      </header>
      {!room ? (
        <p className="phone-wait">Connecting…</p>
      ) : room.status === "lobby" ? (
        <Waiting room={room} />
      ) : room.status === "ended" ? (
        <p className="phone-wait">Game over. Thanks for playing! 🎉</p>
      ) : (
        <LiveLevel room={room} />
      )}
    </main>
  );
}

function JoinForm({ initialCode, notice, onJoined }: { initialCode: string; notice: string; onJoined: (seat: Seat) => void }) {
  const [code, setCode] = useState(initialCode.toUpperCase());
  const [name, setName] = useState("");
  const [team, setTeam] = useState("");
  const [error, setError] = useState("");
  const [joining, setJoining] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setJoining(true);
    setError("");
    try {
      const joined = await joinRoom(code.trim(), name.trim(), team);
      onJoined({ code: joined.code, token: joined.token, playerId: joined.playerId, name: joined.name, team: joined.team });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setJoining(false);
    }
  }

  const ready = code.trim().length === 6 && name.trim() && team;

  return (
    <main className="phone">
      <form className="phone-join" onSubmit={submit}>
        <h1>Join the game</h1>
        {notice && <p className="phone-notice">{notice}</p>}
        <label htmlFor="room-code">Room code</label>
        <input
          id="room-code"
          className="phone-input phone-code"
          value={code}
          maxLength={6}
          autoCapitalize="characters"
          autoComplete="off"
          inputMode="text"
          onChange={(e) => setCode(e.target.value.toUpperCase())}
        />
        <label htmlFor="player-name">Your name</label>
        <input
          id="player-name"
          className="phone-input"
          value={name}
          maxLength={20}
          autoComplete="nickname"
          onChange={(e) => setName(e.target.value)}
        />
        <fieldset className="phone-teams">
          <legend>Your team</legend>
          {TEAMS.map((t) => (
            <button
              key={t}
              type="button"
              className={`phone-team-btn ${team === t ? "on" : ""}`}
              aria-pressed={team === t}
              onClick={() => setTeam(t)}
            >
              {t}
            </button>
          ))}
        </fieldset>
        {error && <p className="sq-error">{error}</p>}
        <button className="btn phone-submit" type="submit" disabled={!ready || joining}>
          {joining ? "Joining…" : "Join"}
        </button>
      </form>
    </main>
  );
}

function Waiting({ room }: { room: RoomState }) {
  const online = room.players.filter((p) => p.online).length;
  return (
    <div className="phone-wait">
      <p className="phone-big">You&apos;re in! 🎉</p>
      <p>
        {online} {online === 1 ? "player" : "players"} here. Waiting for the host to start…
      </p>
    </div>
  );
}

/** Follows the big screen: the current incident, the question, and what just happened. */
function LiveLevel({ room }: { room: RoomState }) {
  const { levels } = useContent();
  const { lvl, phase, picked } = room.quiz;
  const level = levels[lvl];
  const correct = level.options.findIndex((o) => o.correct);
  const revealed = phase === "run" || phase === "learn" || phase === "retry";

  const banner =
    phase === "fail"
      ? "💥 Wrong pick! Watch it break on the big screen."
      : phase === "retry"
        ? "One more try…"
        : phase === "run" || phase === "learn"
          ? `✅ ${level.block} added to the system`
          : "What would you do? Shout it out!";

  return (
    <div className="phone-level">
      <p className="phone-progress">
        Level {lvl} of {levels.length - 1} · <span className="incident-alert">{level.alert}</span>
      </p>
      <h2>{level.question}</h2>
      <ol className="phone-options">
        {level.options.map((o, i) => (
          <li
            key={o.text}
            className={i === picked && phase === "fail" ? "phone-wrong" : revealed && i === correct ? "phone-right" : ""}
          >
            <kbd>{KEYS[i]}</kbd>
            <span>{o.text}</span>
          </li>
        ))}
      </ol>
      <p className={`phone-banner phone-banner-${phase}`}>{banner}</p>
    </div>
  );
}

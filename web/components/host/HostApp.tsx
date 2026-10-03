"use client";

import { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import Game from "@/components/Game";
import { clearSeat, createRoom, loadSeat, saveSeat, useRoom, type RoomState, type Seat } from "@/lib/room";

type HostSeat = Seat & { joinUrl: string };

/** The big screen in a multiplayer game: open a room, show the lobby, then run the game the server owns. */
export function HostApp() {
  const [seat, setSeat] = useState<HostSeat | null>(null);
  const [error, setError] = useState("");
  const [presenter, setPresenter] = useState("");
  const { room, connection, emit, hostAction } = useRoom(seat);

  const openNewRoom = useCallback(async () => {
    setError("");
    clearSeat("host");
    try {
      const created = await createRoom();
      const next = { code: created.code, token: created.hostToken, joinUrl: created.joinUrl };
      saveSeat("host", next);
      setSeat(next);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  // Refreshing the big screen keeps the same room; otherwise open a new one.
  useEffect(() => {
    const saved = loadSeat<HostSeat>("host");
    if (saved) setSeat(saved);
    else openNewRoom();
  }, [openNewRoom]);

  if (error) {
    return (
      <main className="intro">
        <p className="sq-error">Couldn&apos;t open a room: {error}</p>
        <p className="lede">Is the API running? Start it with --host 0.0.0.0 so phones can reach it.</p>
        <button className="btn" onClick={openNewRoom}>
          Try again
        </button>
      </main>
    );
  }

  if (connection === "refused") {
    return (
      <main className="intro">
        <h1 className="intro-label">This room no longer exists</h1>
        <p className="lede">The API was restarted, so its rooms were cleared.</p>
        <button className="btn" onClick={openNewRoom} autoFocus>
          Open a new room
        </button>
      </main>
    );
  }

  if (!seat || !room) {
    return (
      <main className="intro">
        <p className="lede">Opening a room…</p>
      </main>
    );
  }

  if (room.status === "playing") {
    return (
      <>
        <Game remote={{ quiz: room.quiz, dispatch: hostAction }} startAt="briefing" initialName={presenter.trim() || "the host"} />
        <RoomBadge room={room} reconnecting={connection === "reconnecting"} />
      </>
    );
  }

  if (room.status === "ended") {
    return (
      <main className="intro">
        <h1 className="intro-label">Game over. Thanks for playing!</h1>
        <button className="btn" onClick={openNewRoom} autoFocus>
          Open a new room
        </button>
      </main>
    );
  }

  return (
    <Lobby
      room={room}
      joinUrl={seat.joinUrl}
      presenter={presenter}
      onPresenter={setPresenter}
      onStart={() => emit("host:start")}
      onEnd={() => emit("host:end")}
    />
  );
}

function Lobby({
  room,
  joinUrl,
  presenter,
  onPresenter,
  onStart,
  onEnd,
}: {
  room: RoomState;
  joinUrl: string;
  presenter: string;
  onPresenter: (name: string) => void;
  onStart: () => void;
  onEnd: () => void;
}) {
  const online = room.players.filter((p) => p.online).length;
  const joinAddress = joinUrl.replace(/^https?:\/\//, "").replace(/\?.*$/, "");

  return (
    <main className="lobby">
      <section className="lobby-join" aria-label="How to join">
        <span className="chip">Multiplayer</span>
        <h1>Join on your phone</h1>
        <div className="lobby-qr">
          <QRCodeSVG value={joinUrl} size={260} marginSize={2} title={`Join link: ${joinUrl}`} />
        </div>
        <p className="lobby-or">
          or open <b>{joinAddress}</b> and enter
        </p>
        <p className="lobby-code" aria-label={`Room code ${room.code.split("").join(" ")}`}>
          {room.code}
        </p>
      </section>

      <section className="lobby-teams" aria-label="Players">
        <header className="lobby-count">
          <h2>
            {online} {online === 1 ? "player" : "players"} in the room
          </h2>
        </header>
        <div className="lobby-grid">
          {room.teams.map((team) => {
            const members = room.players.filter((p) => p.team === team);
            return (
              <div key={team} className="lobby-team">
                <h3>
                  {team} <span>{members.length}</span>
                </h3>
                <ul>
                  {members.map((p) => (
                    <li key={p.id} className={p.online ? "" : "lobby-offline"}>
                      {p.name}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
        <footer className="lobby-foot">
          <label htmlFor="presenter">Presenter</label>
          <input
            id="presenter"
            className="lobby-input"
            value={presenter}
            maxLength={20}
            placeholder="Your name"
            onChange={(e) => onPresenter(e.target.value)}
          />
          <button className="btn" onClick={onStart}>
            Start the game
          </button>
          <button className="btn-ghost" onClick={onEnd}>
            Close room
          </button>
        </footer>
      </section>
    </main>
  );
}

function RoomBadge({ room, reconnecting }: { room: RoomState; reconnecting: boolean }) {
  const online = room.players.filter((p) => p.online).length;
  return (
    <div className={`room-badge ${reconnecting ? "room-badge-warn" : ""}`} role="status">
      {reconnecting ? "Reconnecting…" : `Room ${room.code} · ${online} online`}
    </div>
  );
}

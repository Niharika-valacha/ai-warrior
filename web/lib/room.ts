// Multiplayer rooms from the browser: HTTP to create/join, Socket.IO for live updates.
import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";
import { apiUrl } from "./apiUrl";
import type { QuizAction, QuizState } from "./quiz";

export type RoomPlayer = { id: string; name: string; team: string; online: boolean };

export type RoomState = {
  code: string;
  status: "lobby" | "playing" | "ended";
  quiz: QuizState;
  players: RoomPlayer[];
  teams: string[];
};

/** Who you are in a room. The token is your identity: it's what lets you reconnect as yourself. */
export type Seat = { code: string; token: string; playerId?: string; name?: string; team?: string };

export type Connection = "connecting" | "connected" | "reconnecting" | "refused";

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${apiUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? `The API returned ${res.status}`);
  return data as T;
}

export const createRoom = () => post<{ code: string; hostToken: string; joinUrl: string }>("/rooms");

export const joinRoom = (code: string, name: string, team: string) =>
  post<{ code: string; playerId: string; name: string; team: string; token: string }>(
    `/rooms/${encodeURIComponent(code)}/players`,
    { name, team },
  );

// Seats survive a refresh or a crashed browser tab. Storage can be unavailable (private mode), so never rely on it.
const seatKey = (role: "host" | "player") => `ai-warrior:${role}-seat`;

export function saveSeat(role: "host" | "player", seat: Seat & { joinUrl?: string }) {
  try {
    localStorage.setItem(seatKey(role), JSON.stringify(seat));
  } catch {}
}

export function loadSeat<T extends Seat = Seat>(role: "host" | "player"): T | null {
  try {
    const raw = localStorage.getItem(seatKey(role));
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function clearSeat(role: "host" | "player") {
  try {
    localStorage.removeItem(seatKey(role));
  } catch {}
}

/**
 * Live room state over Socket.IO. Reconnects automatically (first retry after 250 ms, never waiting
 * more than 2 s). "refused" means the room or token is gone, e.g. the API restarted and rooms were lost.
 */
export function useRoom(seat: Seat | null) {
  const [room, setRoom] = useState<RoomState | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");
  const socketRef = useRef<Socket | null>(null);
  const code = seat?.code;
  const token = seat?.token;

  useEffect(() => {
    if (!code || !token) return;
    const socket = io(apiUrl(), {
      auth: { room: code, token },
      transports: ["websocket"],
      reconnectionDelay: 250,
      reconnectionDelayMax: 2000,
    });
    socketRef.current = socket;
    socket.on("connect", () => setConnection("connected"));
    socket.on("disconnect", () => setConnection("reconnecting"));
    socket.on("connect_error", () => setConnection(socket.active ? "reconnecting" : "refused"));
    socket.on("room", (state: RoomState) => setRoom(state));
    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [code, token]);

  const emit = useCallback((event: string, data?: unknown) => {
    socketRef.current?.emit(event, data);
  }, []);

  /** Host only: the server applies it with the quiz rules and broadcasts the result. */
  const hostAction = useCallback((action: QuizAction) => emit("host:action", action), [emit]);

  return { room, connection, emit, hostAction };
}

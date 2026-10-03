"""Multiplayer rooms: who joined, on which team, who's online, and the quiz state the host drives.

Identity is a secret token handed out on join (host or player). Phones keep it, so a refresh
or a dropped connection reconnects as the same player instead of creating a new one.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from quiz import QuizState

TEAMS = ("QA", "Frontend", "Backend", "Leadership")
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L lookalikes: easy to read off a projector
CODE_LENGTH = 6
MAX_PLAYERS = 200
MAX_NAME = 20

Status = Literal["lobby", "playing", "ended"]


class JoinError(ValueError):
    pass


@dataclass
class Player:
    id: str
    name: str
    team: str
    token: str
    connections: int = 0  # open sockets; a phone can briefly have two while reconnecting

    @property
    def online(self) -> bool:
        return self.connections > 0


@dataclass
class Room:
    code: str
    host_token: str
    status: Status = "lobby"
    quiz: QuizState = field(default_factory=QuizState)
    players: dict[str, Player] = field(default_factory=dict)  # by player id
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        """What every client may see. Never includes tokens."""
        return {
            "code": self.code,
            "status": self.status,
            "quiz": self.quiz.to_json(),
            "players": [{"id": p.id, "name": p.name, "team": p.team, "online": p.online} for p in self.players.values()],
            "teams": list(TEAMS),
        }


class Rooms:
    # ponytail: in-memory, one API instance. Persist to Postgres (Phase 2, when votes matter)
    # and share across instances via Redis (Phase 5). Rooms vanish if the API restarts.

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    def create(self) -> Room:
        code = self._new_code()
        room = Room(code=code, host_token=secrets.token_urlsafe(24))
        self._rooms[code] = room
        return room

    def get(self, code: str) -> Optional[Room]:
        return self._rooms.get(code.strip().upper())

    def join(self, code: str, name: str, team: str) -> Player:
        room = self.get(code)
        if room is None:
            raise JoinError("No room with that code")
        if room.status == "ended":
            raise JoinError("This game has ended")
        if team not in TEAMS:
            raise JoinError(f"Pick a team: {', '.join(TEAMS)}")
        name = " ".join(name.split())[:MAX_NAME]
        if not name:
            raise JoinError("Enter a name")
        if len(room.players) >= MAX_PLAYERS:
            raise JoinError("This room is full")
        player = Player(id=secrets.token_hex(4), name=self._unique_name(room, name), team=team, token=secrets.token_urlsafe(24))
        room.players[player.id] = player
        return player

    def authenticate(self, code: str, token: str) -> Optional[tuple[Room, Optional[Player]]]:
        """(room, None) for the host, (room, player) for a player, None if the token is wrong."""
        room = self.get(code)
        if room is None or not token:
            return None
        if secrets.compare_digest(token, room.host_token):
            return room, None
        player = next((p for p in room.players.values() if secrets.compare_digest(token, p.token)), None)
        return (room, player) if player else None

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self._rooms:
                return code

    @staticmethod
    def _unique_name(room: Room, name: str) -> str:
        taken = {p.name.lower() for p in room.players.values()}
        candidate, n = name, 2
        while candidate.lower() in taken:
            candidate, n = f"{name} {n}", n + 1
        return candidate


rooms = Rooms()

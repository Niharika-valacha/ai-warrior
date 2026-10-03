"""Live rooms over Socket.IO: the server owns the game, clients only send actions.

Socket.IO (python-socketio) gives us rooms, broadcasting, heartbeats and client auto-reconnect.
Every change broadcasts the room's full public state; it's small, and clients stay simple.
"""
from __future__ import annotations

import re

import socketio

import content
from quiz import reduce
from rooms import rooms

# The game on this laptop, or on a phone on the same Wi-Fi (private network addresses).
LOCAL_ORIGIN = re.compile(
    r"^https?://(localhost|127\.0\.0\.1|10(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2})(:\d+)?$"
)


def allowed_origin(origin, environ=None) -> bool:
    return bool(origin) and bool(LOCAL_ORIGIN.match(origin))


sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origin)


def _levels() -> list[dict]:
    with content.connect() as conn:
        return content.read_all(conn)["levels"]


async def broadcast(code: str) -> None:
    room = rooms.get(code)
    if room:
        await sio.emit("room", room.public(), room=room.code)


@sio.event
async def connect(sid, environ, auth):
    """Join the room's channel. `auth` carries {room, token} from the join step."""
    found = rooms.authenticate((auth or {}).get("room", ""), (auth or {}).get("token", ""))
    if found is None:
        raise socketio.exceptions.ConnectionRefusedError("Unknown room or token")
    room, player = found
    await sio.save_session(sid, {"code": room.code, "player_id": player.id if player else None})
    await sio.enter_room(sid, room.code)
    if player:
        player.connections += 1
    await broadcast(room.code)


@sio.event
async def disconnect(sid, reason=None):
    session = await sio.get_session(sid)
    room = rooms.get(session["code"])
    player = room.players.get(session["player_id"]) if room and session["player_id"] else None
    if player:
        player.connections = max(0, player.connections - 1)
        await broadcast(room.code)


async def _host_room(sid):
    """The room, if this socket belongs to its host; None for players (they can't drive the game)."""
    session = await sio.get_session(sid)
    return rooms.get(session["code"]) if session["player_id"] is None else None


@sio.on("host:start")
async def host_start(sid, data=None):
    room = await _host_room(sid)
    if room and room.status == "lobby":
        room.status = "playing"
        await broadcast(room.code)


@sio.on("host:action")
async def host_action(sid, action):
    """The host picked an answer, retried, moved on... The server applies it with the quiz rules."""
    room = await _host_room(sid)
    if room and room.status == "playing" and isinstance(action, dict):
        room.quiz = reduce(room.quiz, action, _levels())
        await broadcast(room.code)


@sio.on("host:end")
async def host_end(sid, data=None):
    room = await _host_room(sid)
    if room:
        room.status = "ended"
        await broadcast(room.code)

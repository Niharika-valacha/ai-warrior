"""Live rooms over Socket.IO: the server owns the game, clients only send actions.

Socket.IO (python-socketio) gives us rooms, broadcasting, heartbeats and client auto-reconnect.
Every change broadcasts the room's public state; it's small, and clients stay simple.

Voting: the host opens a round, phones vote (and may change their minds) until the deadline,
then the server closes it, saves the result and plays the room's pick on the big screen.
"""
from __future__ import annotations

import asyncio
import re
import time

import socketio

import content
from quiz import reduce
from rooms import Room, VoteRound, rooms
from store import Store

VOTE_SECONDS = 20
BROADCAST_EVERY_S = 0.1  # while votes pour in, send at most 10 updates a second per room

# The game on this laptop, or on a phone on the same Wi-Fi (private network addresses).
LOCAL_ORIGIN = re.compile(
    r"^https?://(localhost|127\.0\.0\.1|10(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2})(:\d+)?$"
)


def allowed_origin(origin, environ=None) -> bool:
    return bool(origin) and bool(LOCAL_ORIGIN.match(origin))


sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origin)
store = Store()
_pending_broadcast: set[str] = set()


def _levels() -> list[dict]:
    with content.connect() as conn:
        return content.read_all(conn)["levels"]


async def broadcast(code: str) -> None:
    room = rooms.get(code)
    if room:
        await sio.emit("room", room.public(), room=room.code)


def broadcast_soon(code: str) -> None:
    """Coalesce bursts (a room voting at once) into one update every BROADCAST_EVERY_S."""
    if code in _pending_broadcast:
        return
    _pending_broadcast.add(code)

    async def flush():
        await asyncio.sleep(BROADCAST_EVERY_S)
        _pending_broadcast.discard(code)
        await broadcast(code)

    asyncio.ensure_future(flush())


# ---------------------------------------------------------------- connecting


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
        # A phone that reconnects mid-vote gets its own pick back (votes are private).
        if room.vote and player.id in room.vote.choices:
            await sio.emit("vote:mine", {"roundId": room.vote.round_id, "option": room.vote.choices[player.id]}, to=sid)
    await broadcast(room.code)


@sio.event
async def disconnect(sid, reason=None):
    session = await sio.get_session(sid)
    room = rooms.get(session["code"])
    player = room.players.get(session["player_id"]) if room and session["player_id"] else None
    if player:
        player.connections = max(0, player.connections - 1)
        await broadcast(room.code)


async def _whoami(sid):
    session = await sio.get_session(sid)
    room = rooms.get(session["code"])
    player = room.players.get(session["player_id"]) if room and session["player_id"] else None
    return room, player


async def _host_room(sid):
    """The room, if this socket belongs to its host; None for players (they can't drive the game)."""
    room, player = await _whoami(sid)
    return room if room and player is None else None


# ---------------------------------------------------------------- host controls


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
    if not (room and room.status == "playing" and isinstance(action, dict)):
        return
    if action.get("type") == "pick" and room.vote and room.vote.open:
        return  # the room is voting on this question; the host can close the vote early instead
    room.quiz = reduce(room.quiz, action, _levels())
    if room.vote and room.vote.level != room.quiz.lvl:
        room.vote = None  # moved on (or reset): the old result belongs to the previous question
    await broadcast(room.code)


@sio.on("host:end")
async def host_end(sid, data=None):
    room = await _host_room(sid)
    if room:
        room.status = "ended"
        await store.end_room(room.code)
        await broadcast(room.code)


# ---------------------------------------------------------------- voting


@sio.on("host:open_vote")
async def open_vote(sid, data=None):
    """Put the current question to the room for VOTE_SECONDS."""
    room = await _host_room(sid)
    if not (room and room.status == "playing" and room.quiz.phase == "ask"):
        return
    async with room.lock:
        if room.vote and room.vote.open:
            return
        rnd = await store.open_round(room.code, room.quiz.lvl, eligible=room.online_count(), seconds=VOTE_SECONDS)
        room.vote = VoteRound(round_id=rnd.id, level=room.quiz.lvl, closes_at=time.time() + VOTE_SECONDS, eligible=rnd.eligible)
    asyncio.ensure_future(_close_when_time_is_up(room.code, rnd.id))
    await broadcast(room.code)


@sio.on("host:close_vote")
async def host_close_vote(sid, data=None):
    room = await _host_room(sid)
    if room and room.vote and room.vote.open:
        await close_vote(room)


@sio.on("vote")
async def vote(sid, data):
    """A phone votes or changes its vote. Returns an acknowledgement the phone can show."""
    room, player = await _whoami(sid)
    option = (data or {}).get("option") if isinstance(data, dict) else None
    if not (room and player and isinstance(option, int) and 0 <= option <= 3):
        return {"ok": False, "error": "Not a valid vote"}
    async with room.lock:
        rnd = room.vote
        if not (rnd and rnd.open and time.time() < rnd.closes_at):
            return {"ok": False, "error": "Voting is closed"}
        if not await store.cast_vote(rnd.round_id, player.id, option):
            return {"ok": False, "error": "Voting is closed"}
        rnd.choices[player.id] = option
        everyone_voted = len(rnd.choices) >= room.online_count()
    if everyone_voted:
        await close_vote(room)
    else:
        broadcast_soon(room.code)
    return {"ok": True, "option": option}


async def _close_when_time_is_up(code: str, round_id: int) -> None:
    room = rooms.get(code)
    if not room or not room.vote:
        return
    await asyncio.sleep(max(0.0, room.vote.closes_at - time.time()))
    room = rooms.get(code)
    if room and room.vote and room.vote.round_id == round_id and room.vote.open:
        await close_vote(room)


async def close_vote(room: Room) -> None:
    """Lock the round, count it in the database, and play the room's pick on the big screen."""
    async with room.lock:
        rnd = room.vote
        if not rnd or not rnd.open:
            return
        counts, top = await store.close_round(rnd.round_id)
        voters = sum(counts)
        rnd.result = {
            "counts": counts,
            "top": top,
            "voters": voters,
            "participation": round(voters / rnd.eligible, 2) if rnd.eligible else 0.0,
        }
        if top is not None:
            room.quiz = reduce(room.quiz, {"type": "pick", "option": top}, _levels())
    await broadcast(room.code)

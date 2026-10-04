"""Saving multiplayer games: rooms, players, voting rounds and votes (SQLAlchemy, async).

DATABASE_URL picks the database: Postgres via `docker compose up -d`, or a local SQLite file when unset,
so the game also runs without Docker. Schema changes go through Alembic (api/migrations).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from models import Base, GamePlayer, GameRoom, Round, Vote

DEFAULT_URL = f"sqlite+aiosqlite:///{Path(__file__).parent / 'data' / 'game.db'}"


def now() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, url: Optional[str] = None):
        self.engine: AsyncEngine = create_async_engine(url or os.environ.get("DATABASE_URL", DEFAULT_URL))
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_tables(self) -> None:
        """For tests and quick local runs. Real databases are migrated with `alembic upgrade head`."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    # ---------------------------------------------------------------- rooms and players

    async def add_room(self, code: str) -> None:
        async with self.session.begin() as s:
            s.add(GameRoom(code=code))

    async def end_room(self, code: str) -> None:
        async with self.session.begin() as s:
            await s.execute(update(GameRoom).where(GameRoom.code == code).values(ended_at=now()))

    async def add_player(self, room_code: str, player_id: str, name: str, team: str) -> None:
        async with self.session.begin() as s:
            s.add(GamePlayer(id=player_id, room_code=room_code, name=name, team=team))

    # ---------------------------------------------------------------- voting rounds

    async def open_round(self, room_code: str, level: int, eligible: int, seconds: int) -> Round:
        opened = now()
        rnd = Round(room_code=room_code, level=level, opened_at=opened, closes_at=opened + timedelta(seconds=seconds), eligible=eligible)
        async with self.session.begin() as s:
            s.add(rnd)
        return rnd

    async def cast_vote(self, round_id: int, player_id: str, option: int) -> bool:
        """Record or change a vote. False if the round is already closed.

        One statement, so it's safe under concurrency: the insert only happens while the round is open,
        and the (round, player) primary key turns a second vote into an update instead of a duplicate.
        On Postgres the vote also takes a shared lock on its round, so closing the round waits for votes
        already in flight, and any vote after that sees the round closed. (SQLite runs writes one at a time.)
        """
        lock = "FOR SHARE" if self.engine.dialect.name == "postgresql" else ""
        sql = text(
            f"""
            INSERT INTO votes (round_id, player_id, option, changes, voted_at)
            SELECT :round_id, :player_id, :option, 0, :at
            FROM rounds WHERE id = :round_id AND closed_at IS NULL {lock}
            ON CONFLICT (round_id, player_id)
            DO UPDATE SET option = excluded.option, changes = votes.changes + 1, voted_at = excluded.voted_at
            """
        )
        async with self.session.begin() as s:
            result = await s.execute(sql, {"round_id": round_id, "player_id": player_id, "option": option, "at": now()})
        return result.rowcount == 1

    async def tally(self, round_id: int) -> list[int]:
        """Votes per option (A–D), counted in the database."""
        async with self.session() as s:
            rows = await s.execute(
                select(Vote.option, text("count(*)")).where(Vote.round_id == round_id).group_by(Vote.option)
            )
        counts = [0, 0, 0, 0]
        for option, n in rows:
            counts[option] = n
        return counts

    async def close_round(self, round_id: int) -> tuple[list[int], Optional[int]]:
        """Lock the round, then count. Returns (votes per option, the room's pick or None if nobody voted).
        Ties go to the earliest option, so the result never depends on timing."""
        async with self.session.begin() as s:
            await s.execute(update(Round).where(Round.id == round_id, Round.closed_at.is_(None)).values(closed_at=now()))
        counts = await self.tally(round_id)
        voters = sum(counts)
        top = counts.index(max(counts)) if voters else None
        async with self.session.begin() as s:
            await s.execute(update(Round).where(Round.id == round_id).values(voters=voters, top_option=top))
        return counts, top

    async def get_round(self, round_id: int) -> Optional[Round]:
        async with self.session() as s:
            return await s.get(Round, round_id)

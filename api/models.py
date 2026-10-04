"""The multiplayer data that must outlive a game: who played, every question asked, every vote.

Live room state (who's online, the current quiz phase) stays in memory in rooms.py; this is the record.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GameRoom(Base):
    __tablename__ = "rooms"

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class GamePlayer(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    room_code: Mapped[str] = mapped_column(ForeignKey("rooms.code", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    team: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Round(Base):
    """One question put to the room: open for a fixed time, then closed and tallied."""

    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(ForeignKey("rooms.code", ondelete="CASCADE"), index=True)
    level: Mapped[int]
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    eligible: Mapped[int]  # players online when it opened: the denominator of participation
    voters: Mapped[Optional[int]]  # set when it closes
    top_option: Mapped[Optional[int]]  # what the room picked


class Vote(Base):
    """One player's answer to one round. The composite primary key makes double votes impossible."""

    __tablename__ = "votes"
    __table_args__ = (CheckConstraint("option BETWEEN 0 AND 3", name="vote_option_range"),)

    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    option: Mapped[int]
    changes: Mapped[int] = mapped_column(default=0)  # how often they changed their mind
    voted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

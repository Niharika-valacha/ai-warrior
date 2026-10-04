"""Votes under pressure. SQLite by default; set TEST_DATABASE_URL to run the same checks on Postgres:

    TEST_DATABASE_URL=postgresql+asyncpg://aiwarrior:aiwarrior@127.0.0.1:5435/aiwarrior_test .venv/bin/python -m unittest test_store
"""
import asyncio
import os
import secrets
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from models import Base, Vote
from store import Store

URL = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"


class StoreTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = Store(URL)
        async with self.store.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        self.room = secrets.token_hex(3).upper()
        await self.store.add_room(self.room)

    async def asyncTearDown(self):
        await self.store.close()

    async def players(self, n):
        ids = [f"p{i}" for i in range(n)]
        for pid in ids:
            await self.store.add_player(self.room, pid, pid, "QA")
        return ids

    async def rows(self, round_id):
        async with self.store.session() as s:
            return (await s.execute(select(func.count()).select_from(Vote).where(Vote.round_id == round_id))).scalar()

    async def test_changing_your_vote_updates_it_instead_of_adding_one(self):
        (pid,) = await self.players(1)
        rnd = await self.store.open_round(self.room, level=0, eligible=1, seconds=20)
        for option in (0, 2, 3):
            self.assertTrue(await self.store.cast_vote(rnd.id, pid, option))
        self.assertEqual(await self.rows(rnd.id), 1)
        self.assertEqual(await self.store.tally(rnd.id), [0, 0, 0, 1])

    async def test_a_closed_round_refuses_votes(self):
        (pid,) = await self.players(1)
        rnd = await self.store.open_round(self.room, level=0, eligible=1, seconds=20)
        await self.store.close_round(rnd.id)
        self.assertFalse(await self.store.cast_vote(rnd.id, pid, 1))
        self.assertEqual(await self.rows(rnd.id), 0)

    async def test_fifty_players_voting_at_once_lose_nothing_and_double_count_nothing(self):
        ids = await self.players(50)
        rnd = await self.store.open_round(self.room, level=0, eligible=50, seconds=20)
        final = {pid: i % 4 for i, pid in enumerate(ids)}
        # Everyone votes at once; the first 20 also change their minds, concurrently.
        first = [self.store.cast_vote(rnd.id, pid, (final[pid] + 1) % 4) for pid in ids[:20]]
        await asyncio.gather(*first)
        await asyncio.gather(*[self.store.cast_vote(rnd.id, pid, final[pid]) for pid in ids])
        counts, top = await self.store.close_round(rnd.id)
        expected = [list(final.values()).count(o) for o in range(4)]
        self.assertEqual(counts, expected)
        self.assertEqual(await self.rows(rnd.id), 50)
        self.assertEqual(top, 0)  # 13 / 13 / 12 / 12: the tie goes to the earliest option

    async def test_closing_mid_storm_counts_exactly_the_votes_that_got_in(self):
        ids = await self.players(60)
        rnd = await self.store.open_round(self.room, level=0, eligible=60, seconds=20)
        votes = [self.store.cast_vote(rnd.id, pid, 1) for pid in ids]
        results = await asyncio.gather(*votes[:30], self.store.close_round(rnd.id), *votes[30:])
        accepted = sum(1 for r in results if r is True)
        counts, _ = await self.store.close_round(rnd.id)  # closing again is harmless
        self.assertEqual(sum(counts), accepted)  # every accepted vote is counted...
        self.assertEqual(await self.rows(rnd.id), accepted)  # ...and nothing else got stored
        self.assertFalse(await self.store.cast_vote(rnd.id, ids[0], 2))

    async def test_nobody_voting_means_no_pick(self):
        rnd = await self.store.open_round(self.room, level=0, eligible=5, seconds=20)
        self.assertEqual(await self.store.close_round(rnd.id), ([0, 0, 0, 0], None))
        saved = await self.store.get_round(rnd.id)
        self.assertEqual((saved.voters, saved.top_option, saved.eligible), (0, None, 5))

    async def test_the_database_rejects_an_impossible_option(self):
        (pid,) = await self.players(1)
        rnd = await self.store.open_round(self.room, level=0, eligible=1, seconds=20)
        with self.assertRaises(IntegrityError):
            await self.store.cast_vote(rnd.id, pid, 7)


if __name__ == "__main__":
    unittest.main()

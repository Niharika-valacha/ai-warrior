"""Live rooms end to end: a real server, a real host and real players over Socket.IO."""
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

os.environ.setdefault("CONTENT_DB", str(Path(tempfile.mkdtemp()) / "content.db"))
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{Path(tempfile.mkdtemp()) / 'game.db'}")

import httpx  # noqa: E402
import socketio  # noqa: E402
import uvicorn  # noqa: E402

import main  # noqa: E402
import realtime  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(condition, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    raise AssertionError("timed out waiting for the condition")


class Client:
    """A Socket.IO client that remembers the last room state it was sent."""

    def __init__(self, base, code, token):
        self.room = None
        self.mine = None  # private "your vote" message after a reconnect
        self.sio = socketio.Client(reconnection=False)
        self.sio.on("room", lambda data: setattr(self, "room", data))
        self.sio.on("vote:mine", lambda data: setattr(self, "mine", data))
        self.sio.connect(base, auth={"room": code, "token": token}, transports=["websocket"])

    def online_names(self):
        return sorted(p["name"] for p in self.room["players"] if p["online"]) if self.room else []


class LiveServerTest(unittest.TestCase):
    """Starts the real API (HTTP + Socket.IO) once per class; each test gets a fresh room."""

    @classmethod
    def setUpClass(cls):
        port = free_port()
        cls.base = f"http://127.0.0.1:{port}"
        cls.server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        wait_for(lambda: cls.server.started, timeout=10)
        cls.http = httpx.Client(base_url=cls.base)
        # Every test opens a room from 127.0.0.1; lift the per-IP limits for the test server only.
        for limit in (main.ROOM_LIMIT, main.JOIN_LIMIT):
            limit.limit = 10_000

    @classmethod
    def tearDownClass(cls):
        cls.http.close()
        cls.server.should_exit = True
        cls.thread.join(timeout=5)

    def setUp(self):
        room = self.http.post("/rooms").json()
        self.code, self.host_token = room["code"], room["hostToken"]
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            if c.sio.connected:
                c.sio.disconnect()

    def connect(self, token):
        client = Client(self.base, self.code, token)
        self.clients.append(client)
        return client

    def join(self, name, team="QA"):
        res = self.http.post(f"/rooms/{self.code}/players", json={"name": name, "team": team})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()


class RealtimeTest(LiveServerTest):
    def test_players_join_and_the_host_sees_them_live(self):
        host = self.connect(self.host_token)
        for name in ("Asha", "Ben", "Chen"):
            self.connect(self.join(name)["token"])
        wait_for(lambda: host.online_names() == ["Asha", "Ben", "Chen"])

    def test_host_drives_the_game_and_every_phone_follows(self):
        host = self.connect(self.host_token)
        phone = self.connect(self.join("Asha")["token"])
        host.sio.emit("host:start")
        wait_for(lambda: phone.room and phone.room["status"] == "playing")
        host.sio.emit("host:action", {"type": "pick", "option": 0})  # option A is wrong on level 0
        wait_for(lambda: phone.room["quiz"]["phase"] == "fail")

    def test_a_player_cannot_drive_the_game(self):
        host = self.connect(self.host_token)
        phone = self.connect(self.join("Mallory")["token"])
        phone.sio.emit("host:start")
        phone.sio.emit("host:action", {"type": "pick", "option": 3})
        host.sio.emit("host:end")  # a later event from the host proves the player's ones were processed and ignored
        wait_for(lambda: host.room and host.room["status"] == "ended")
        self.assertEqual(host.room["quiz"]["phase"], "ask")

    def test_a_dropped_phone_reconnects_as_the_same_player(self):
        host = self.connect(self.host_token)
        token = self.join("Asha")["token"]
        phone = self.connect(token)
        wait_for(lambda: host.online_names() == ["Asha"])
        phone.sio.disconnect()
        wait_for(lambda: host.online_names() == [])
        self.connect(token)
        wait_for(lambda: host.online_names() == ["Asha"])
        self.assertEqual(len(host.room["players"]), 1)  # same player, not a new one

    def test_tokens_never_leak_and_bad_tokens_are_refused(self):
        host = self.connect(self.host_token)
        self.connect(self.join("Asha")["token"])
        wait_for(lambda: host.online_names() == ["Asha"])
        self.assertNotIn("token", str(host.room))
        with self.assertRaises(socketio.exceptions.ConnectionError):
            Client(self.base, self.code, "not-a-real-token")

    def test_join_validates_team_and_name(self):
        self.assertEqual(self.http.post(f"/rooms/{self.code}/players", json={"name": "A", "team": "Sales"}).status_code, 400)
        self.assertEqual(self.http.post(f"/rooms/{self.code}/players", json={"name": "   ", "team": "QA"}).status_code, 400)
        self.assertEqual(self.http.post("/rooms/NOPE99/players", json={"name": "A", "team": "QA"}).status_code, 400)
        self.assertEqual(self.join("Asha")["name"], "Asha")
        self.assertEqual(self.join("asha")["name"], "asha 2")  # duplicate names get a number


class VotingTest(LiveServerTest):
    """Phones vote; the server counts, closes and plays the room's pick."""

    def start_game(self, *names):
        host = self.connect(self.host_token)
        phones = [self.connect(self.join(n)["token"]) for n in names]
        wait_for(lambda: len(host.online_names()) == len(names))
        host.sio.emit("host:start")
        wait_for(lambda: host.room["status"] == "playing")
        return host, phones

    def open_vote(self, host):
        host.sio.emit("host:open_vote")
        wait_for(lambda: host.room["vote"] and host.room["vote"]["open"])

    def vote(self, phone, option):
        return phone.sio.call("vote", {"option": option}, timeout=3)

    def test_everyone_votes_and_the_room_pick_plays(self):
        host, phones = self.start_game("Asha", "Ben", "Chen")
        self.open_vote(host)
        for phone, option in zip(phones, (0, 0, 3)):  # A is wrong on level 0, D is right
            self.assertEqual(self.vote(phone, option), {"ok": True, "option": option})
        wait_for(lambda: not host.room["vote"]["open"])  # closes as soon as everyone has voted
        result = host.room["vote"]["result"]
        self.assertEqual((result["counts"], result["top"], result["participation"]), ([2, 0, 0, 1], 0, 1.0))
        self.assertEqual(host.room["quiz"]["phase"], "fail")  # the room picked A, so it breaks on screen

    def test_changing_your_mind_moves_your_vote(self):
        host, (asha, ben) = self.start_game("Asha", "Ben")
        self.open_vote(host)
        self.vote(asha, 0)
        self.vote(asha, 3)
        wait_for(lambda: host.room["vote"]["counts"] == [0, 0, 0, 1])
        self.vote(ben, 3)
        wait_for(lambda: not host.room["vote"]["open"])
        self.assertEqual(host.room["quiz"]["phase"], "run")  # the room got it right

    def test_the_timer_closes_the_vote_and_late_votes_are_refused(self):
        realtime.VOTE_SECONDS = 1
        self.addCleanup(setattr, realtime, "VOTE_SECONDS", 20)
        host, (asha, ben) = self.start_game("Asha", "Ben")
        self.open_vote(host)
        self.vote(asha, 3)
        wait_for(lambda: not host.room["vote"]["open"], timeout=4)
        self.assertEqual(host.room["vote"]["result"]["participation"], 0.5)
        self.assertEqual(self.vote(ben, 0), {"ok": False, "error": "Voting is closed"})

    def test_the_host_cannot_override_an_open_vote(self):
        host, (asha, ben) = self.start_game("Asha", "Ben")
        self.open_vote(host)
        host.sio.emit("host:action", {"type": "pick", "option": 3})
        self.vote(asha, 0)
        wait_for(lambda: host.room["vote"]["voters"] == 1)
        self.assertEqual(host.room["quiz"]["phase"], "ask")

    def test_a_phone_that_reconnects_mid_vote_gets_its_pick_back(self):
        host, (asha, ben) = self.start_game("Asha", "Ben")
        self.open_vote(host)
        self.vote(asha, 2)
        asha.sio.disconnect()
        again = self.connect(self.asha_token)
        wait_for(lambda: again.mine is not None)
        self.assertEqual(again.mine["option"], 2)

    def test_votes_stay_anonymous(self):
        host, (asha, ben) = self.start_game("Asha", "Ben")
        self.open_vote(host)
        self.vote(asha, 1)
        wait_for(lambda: host.room["vote"]["voters"] == 1)
        self.assertNotIn("choices", str(host.room))
        self.assertTrue(all(set(p) == {"id", "name", "team", "online"} for p in host.room["players"]))

    def join(self, name, team="QA"):
        joined = super().join(name, team)
        if name == "Asha":
            self.asha_token = joined["token"]
        return joined


if __name__ == "__main__":
    unittest.main()

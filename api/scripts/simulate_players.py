"""Fill a room with simulated phones against a running API and report the numbers Phase 1 promises.

    cd api && .venv/bin/python scripts/simulate_players.py --players 50

Measures: time for everyone to join and connect, how fast a host action reaches every phone,
and how fast dropped phones reconnect as the same players.
"""
import argparse
import statistics
import threading
import time

import httpx
import socketio


class Phone:
    """One simulated player. Records when it sees the quiz reach a given phase."""

    def __init__(self, base, code, token):
        self.base, self.code, self.token = base, code, token
        self.seen_at = {}
        self.sio = socketio.Client(reconnection=False)
        self.sio.on("room", self._on_room)

    def _on_room(self, room):
        self.seen_at.setdefault(room["quiz"]["phase"], time.perf_counter())

    def connect(self):
        self.sio.connect(self.base, auth={"room": self.code, "token": self.token}, transports=["websocket"])


def wait_until(condition, timeout=15.0):
    deadline = time.time() + timeout
    while not condition():
        if time.time() > deadline:
            raise TimeoutError("condition not met in time")
        time.sleep(0.005)


def ms(seconds):
    return f"{seconds * 1000:.0f} ms"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", type=int, default=50)
    parser.add_argument("--drop", type=int, default=10, help="phones to disconnect and reconnect")
    parser.add_argument("--base", default="http://localhost:8400")
    args = parser.parse_args()

    http = httpx.Client(base_url=args.base, timeout=10)
    room = http.post("/rooms").json()
    code = room["code"]

    host_state = {}
    host = socketio.Client(reconnection=False)
    host.on("room", lambda r: host_state.update(r))
    host.connect(args.base, auth={"room": code, "token": room["hostToken"]}, transports=["websocket"])
    online = lambda: sum(p["online"] for p in host_state.get("players", []))  # noqa: E731

    # 1. Everyone joins and connects (in parallel, like a room scanning a QR code).
    teams = ["QA", "Frontend", "Backend", "Leadership"]
    start = time.perf_counter()
    phones = []
    for i in range(args.players):
        res = http.post(f"/rooms/{code}/players", json={"name": f"Player {i}", "team": teams[i % 4]})
        if res.status_code != 200:
            # All simulated phones share this machine's IP, so the per-IP join limit applies to all of them.
            raise SystemExit(f"Join {i} refused ({res.status_code}): {res.json().get('detail')}")
        token = res.json()["token"]
        phones.append(Phone(args.base, code, token))
    threads = [threading.Thread(target=p.connect) for p in phones]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wait_until(lambda: online() == args.players)
    join_time = time.perf_counter() - start

    # 2. The host acts; how long until every phone has it?
    host.emit("host:start")
    wait_until(lambda: host_state.get("status") == "playing")
    sent = time.perf_counter()
    host.emit("host:action", {"type": "pick", "option": 0})
    wait_until(lambda: all("fail" in p.seen_at for p in phones))
    fanout = sorted(p.seen_at["fail"] - sent for p in phones)

    # 3. Drop some phones, then bring them back with the same tokens.
    dropped = phones[: args.drop]
    for p in dropped:
        p.sio.disconnect()
    wait_until(lambda: online() == args.players - args.drop)
    reconnect_times = []
    for p in dropped:
        again = Phone(args.base, code, p.token)
        t0 = time.perf_counter()
        again.connect()
        reconnect_times.append(time.perf_counter() - t0)
        phones.append(again)
    wait_until(lambda: online() == args.players)
    same_players = len(host_state["players"]) == args.players

    print(f"\nRoom {code}: {args.players} simulated phones\n")
    print(f"  all joined and connected      {ms(join_time)}")
    print(f"  host action → every phone     p50 {ms(statistics.median(fanout))} · p95 {ms(fanout[int(len(fanout) * 0.95) - 1])} · max {ms(fanout[-1])}")
    print(f"  reconnect after a drop        p50 {ms(statistics.median(reconnect_times))} · max {ms(max(reconnect_times))}")
    print(f"  reconnected as same players   {'yes' if same_players else 'NO'}  ({len(host_state['players'])} players in the room)\n")

    for p in phones:
        if p.sio.connected:
            p.sio.disconnect()
    host.disconnect()


if __name__ == "__main__":
    main()

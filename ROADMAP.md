# AI Warrior v2: Roadmap

**Vision:** a live multiplayer game where teams learn GenAI engineering by watching an AI system get built, and break. The host runs it on the big screen; everyone plays from their phone; teams compete on a leaderboard.

**Why v2:** in the first live session, the room mostly watched. Only the presenter could act, and nobody wanted to shout a wrong answer in front of leadership. v2 makes every person a player and makes being wrong anonymous.

**Two audiences, one product:**
- **Teams** get a session that's fun, fast (5–6 levels) and ends with a report on what the team misunderstands.
- **Hiring managers** get proof: real usage numbers, load-test results and a write-up of the iteration.

**Rules for every phase:**
1. Each phase ships something usable on its own.
2. Each phase ends with a **number** (latency, players, participation, accuracy), not just "it works".
3. Cost stays at **$0**: free tiers only, LLM calls cached, replay fallback everywhere.

**The KPI that tells the story:** *participation rate* = players who voted ÷ players in the room, per question.

---

## Phase 0: Ship v1 publicly
Get a live link before adding anything.
- [x] CI: GitHub Actions runs the API and web tests on every PR
- [ ] Deploy the web app (Vercel, free) and the API (Render or Fly.io, free tier)
- [x] Free LLM provider chain: Groq → Gemini → replay model, configured in `.env`
- [x] Rate limiting on the public API (X-ray, side quests, Ask live)

**Done when:** anyone can play v1 at a public URL, and a failed provider falls through to the next one (tested).
**Shows:** CI/CD, deployment, cost control, model routing and fallbacks.

## Phase 1: Rooms and joining
- [ ] Host creates a room → big screen shows a QR code and a room code
- [ ] Players join from their phone: name + team (QA / Frontend / Backend)
- [ ] WebSocket connection per player; live "who's here" list on the host screen
- [ ] **Server-authoritative state:** the quiz reducer (`web/lib/quiz.ts`) moves to the server; phones only send actions
- [ ] Reconnect: refresh the phone mid-game and land back in the same state
- [ ] Postgres (Neon or Supabase free tier) for rooms, players and sessions

**Done when:** 50 simulated players join one room and stay connected; a dropped connection recovers in under 2 seconds.
**Shows:** real-time systems, state ownership, resilience.

## Phase 2: Live voting
- [ ] Question appears on every phone at the same moment, with a 20-second timer
- [ ] One vote per player, changeable until the timer ends, then locked by the server
- [ ] Host screen shows a live bar chart of votes filling in
- [ ] Reveal: the room's top answer plays out (fail script or run log) on the big screen
- [ ] Participation rate recorded for every question

**Done when:** concurrency tests prove no double votes and no lost votes; votes reach the host screen in under 200 ms locally.
**Shows:** correctness under concurrency, event design.

## Phase 3: Scoring and leaderboards
- [ ] Points for a right answer + speed bonus; first-try streaks
- [ ] Team score = average of its members (big teams don't win by size)
- [ ] Leaderboard between levels; podium at the end
- [ ] Session "playlists": pick 5–6 levels for a 20-minute session

**Done when:** scores are reproducible from the stored votes alone (recompute matches live).
**Shows:** domain modeling, event sourcing.

## Phase 4: Host report
- [ ] Events table: joins, votes, reveals, X-ray and side-quest opens
- [ ] After the session: participation per question, the most-picked wrong answers ("70% of your team thinks fine-tuning fixes hallucinations"), team comparison
- [ ] Shareable report page for the host

**Done when:** a finished session produces its report in under 1 second.
**Shows:** data modeling, analytics, product thinking.

## Phase 5: Scale and proof
- [ ] Load test: 500 players in one room (k6 or Locust); publish p50/p95 vote latency and messages/second in the README
- [ ] Observability: structured logs, request and WebSocket metrics, an error dashboard
- [ ] Public demo room with bot players, so a visitor can try it in 30 seconds
- [ ] Horizontal scaling plan: Redis pub/sub between API instances (build it only if the load test needs it)

**Done when:** the README shows real load-test numbers and a live demo room.
**Shows:** performance engineering, production ownership.

## Phase 6: AI features
- [ ] Free-text answers ("Why did this break?") graded by an LLM
- [ ] **Evals for the grader:** a labeled set of answers; publish how often it agrees with human grading
- [ ] Prompt-injection defense for player answers (players will try)
- [ ] Mission builder: describe a scenario → LLM drafts levels → human review → publish

**Done when:** the grader agrees with human labels on at least 90% of the eval set.
**Shows:** AI engineering done properly, with evals and guardrails.

## Phase 7: Launch
- [ ] Run v2 at the next AI guild session; measure participation vs. v1
- [ ] Write-up: "I shipped it, it flopped, here's why, here's v2, here are the numbers"
- [ ] 60-second demo video
- [ ] Season 2 content (the 37 locked topics)

**Done when:** the write-up is published with real numbers from a real session.

---

## Decisions to make before Phase 1
- **Real-time transport:** FastAPI WebSockets on one instance first (simplest), Redis only if Phase 5 needs it.
- **Database:** Postgres for multiplayer data; keep SQLite for local development, or move fully.
- **Hosting:** the API host must support long-lived WebSocket connections (Vercel's serverless functions don't).

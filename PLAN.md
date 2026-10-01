# AI Warrior Quiz: Build Plan

Presenter-driven quiz game for the AI Guild session. Questions live in [QUIZ.md](QUIZ.md).

## Decisions
- **Style:** retro arcade (pixel font, dark background, neon glow)
- **Avatars:** original pixel-art chibi characters, Backend-kun 🍜 and Prompt-chan ✨ (no copyrighted anime)
- **Frontend:** Next.js (React)
- **Backend:** FastAPI (Python). The real FoodieGo system code lives here.
- **DB:** SQLite (stdlib `sqlite3`, one file, no install) for orders/payments. Policies + golden chats as JSON.
- **LLM:** Groq (OpenAI-compatible), model `openai/gpt-oss-120b`. Key in `api/.env` (git-ignored), never in the browser.
- **Right answers:** real Python runs against the FoodieGo data. X-ray shows that exact function (`inspect.getsource`) and its real trace.
- **Wrong answers:** prewritten fail scripts + a pun. Then Try Again shows only the right option.
- **Stage safety:** every live LLM call has a recorded fallback (timeout → replay).
- **Bonus topics for free:** streaming, fallbacks, observability (X-ray = tracing), prompt caching (Level 8 card).

## Structure
```
api/                        FastAPI (Python 3.9, venv in api/.venv)
  main.py                   routes: /content, /xray/{level}, admin edits (/docs)
  content.py                quiz content in SQLite (data/content.db): levels, options, skill_topics, sidekicks, copy
  system.py                 the real FoodieGo agent code shown in X-ray
  llm.py / replay.py        Groq call with replay fallback / deterministic stand-in model
  sidequests.py / tavily.py side quests: web research + Groq writing + cache; live follow-ups
  pipeline.py               Level 0 data pipeline: ingest, clean, redact PII, label, baseline, requirements
  db.py                     FoodieGo demo database (in-memory SQLite per run)
  tracer.py                 step recording for X-ray
  demos.py                  one demo per level
  intents.py                shared intent keywords
  export_snapshots.py       writes web snapshots + content.seed.json
  data/                     chats, policies, golden set, content.seed.json
  test_system.py, test_content.py
web/                        Next.js 16 (port 4000)
  app/page.tsx              server: loads content from the API (snapshot fallback) → <Game />
  components/Game.tsx       screen flow
  components/screens/       one file per screen
  components/level/         OptionList, RunTerminal, ConceptCard, XrayPanel
  components/shell/         GameLayout, SystemPipeline, Buddy
  components/ContentProvider.tsx   useContent() for levels + skill tree
  lib/                      quiz state machine (+ test), loadContent, xray client, hooks, types
  data/                     generated snapshots only (content, xray)
  public/avatars/           6 Stitch mascot images
```

## Editing content (no frontend changes)
1. Open http://localhost:8400/docs → pick an endpoint → "Try it out"
2. Put `ADMIN_TOKEN` from `api/.env` in the `x-admin-token` field
3. `PATCH /levels/{id}`, `PATCH /levels/{id}/options/{position}`, `POST/PATCH/DELETE /skill-topics`,
   `PATCH /sidekicks/{id}`, `PUT /copy/{screen}` (intro, briefing, reactions, boss, tree, win; supports `{name}`, `{levels}`, `**bold**`)
4. Refresh the game. Then run `.venv/bin/python export_snapshots.py` so the stage fallback and git get the change.

The database enforces: exactly one right answer per level, wrong answers must have a fail script and pun, positions 0–3.

---

## Phase 1: Skeleton (playable game)
- [x] Next.js app, retro arcade theme, question panel (left) + system blocks panel (right)
- [x] Intro "Let's play a game" → warrior name → pick avatar
- [x] Two pixel-art avatars (inline SVG) with reactions: idle, cry (wrong), flex (right)
- [x] All 11 levels from QUIZ.md in `levels.ts`
- [x] Wrong → fail script (skippable) → pun → Try Again → only the right option stays
- [x] Right → block drops in → Run log → learn note → concept card

**Done when:** you can click from the intro to Level 10 with no dead ends (all scripted, no backend yet).

## Phase 2: Real code (the engineer flex)
- [x] FastAPI app + `db.py` → fresh in-memory SQLite per run (orders, payments, refunds, audit log)
- [x] `data/`: chats.json (30 chats), policies.json (8 sections), golden.json (20 eval cases)
- [x] `system.py`: real code per level, each calling `trace(label, **values)`; `replay.py` stands in for the LLM
- [x] `GET /xray/{level}` returns output + trace + source; `export_xray.py` snapshots it for stage safety
- [x] X-ray mode in the UI: code on top, step through the trace (back / step / play all)
- [ ] Wrong-answer X-ray: short pseudocode marked `# ❌ the wrong way` (deferred)

**Done when:** every right answer's X-ray shows real Python and the real values it produced.

## Phase 3: Live Groq (the wow moment)
- [x] `llm.py` calls Groq (stdlib HTTP, no SDK) with tools, JSON mode and message conversion
- [x] Any error or 12s timeout → falls back to the replay model, per call
- [x] Live levels: 1, 2, 3, 4, 5, 7. Levels 0, 6, 8, 9, 10 stay on replay on purpose (9 must show the model fooled; 10 = 15 calls)
- [x] X-ray badge shows Live/Snapshot and which model answered (e.g. `openai/gpt-oss-120b`, `replay`)
- [ ] Token-by-token streaming (the terminal already types out line by line; real streaming deferred)

**Done:** works live with the key; with a bad key it falls back to replay; with the API down it falls back to the snapshot.

## Phase 4: Finale
- [x] "Who made this quiz?" with the runaway Niharika button, then Claude
- [x] Meme screen (placeholder until `web/public/meme.jpg` exists) → Finish
- [x] **Skill tree teaser:** all 73 topics as a tree. The ~30 covered today glow ✅ unlocked, the rest are 🔒 "coming soon". Unlocked ones animate in one by one.
- [x] Keyboard shortcuts: `1-4` pick · `Enter`/`N` next · `S` skip · `X` x-ray · `← → P Esc` inside x-ray

**Done when:** the ending gets a laugh, and the tree makes people want the next session.

## Phase 5: Side quests
- [x] `api/sidequests.py`: Tavily web search (4 queries) → Groq writes 6 chapters from those sources only → Pydantic validation (1 retry) → cached in `side_quests`
- [x] Chapters: the story, before & after, in production, for your role (QA/frontend/backend/leadership), tools to try (+ "How I built this game"), at scale (the model is ~N% of it)
- [x] Clickable `[n]` citations; all sources listed
- [x] "Ask live" follow-up box: fresh Tavily search + Groq answer with sources, not cached
- [x] Refresh button (30s cooldown); `Q` opens it from the concept card
- [x] No keys / outage → honest error, never a made-up answer; API down → saved copy from the snapshot
- [ ] Polish learn notes and concept cards to a more professional tone

**Before the session:** open every side quest once (or run the warm-up), then `python export_snapshots.py`.
Groq free tier ≈ 1 side quest per minute (HTTP 429 otherwise).

## Phase 6: Rehearsal
- [ ] Full run on your laptop + projector resolution check
- [ ] Pick the 3–4 levels you fail on purpose (suggested: 0, 4, 9, 10)
- [ ] Time it (target ~20 min)

---

## Open items
- Meme image
- Finish screen text
- Session slot length

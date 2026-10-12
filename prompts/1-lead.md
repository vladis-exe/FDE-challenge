You are the LEAD session for this repo. Three worker sessions (engine, app, evals) run in parallel in the same working tree. You coordinate, integrate and review; you write very little feature code yourself.

First read CLAUDE.md, docs/process-design.md and every file in docs/coordination/.

Then do L1 (bootstrap) from BOARD.md right away. The workers are waiting for it. When it's committed, update status/lead.md and tell me "L1 done" so I can start the other sessions.

After L1, work in this loop until the project ships:

1. Every time you come back, read all status files. If a lane reports a finished task:
   - Review its commit for contract adherence, simplicity, tests, and anything I couldn't explain in a live review.
   - Run `uv run pytest` and `uv run ruff check .`.
   - Tick the task in BOARD.md and write findings under "Review notes for lanes" in status/lead.md.
2. Route what the lanes ask for:
   - Dependency requests: you edit pyproject.toml and run `uv sync`.
   - Contract change requests: you edit CONTRACTS.md, bump its version, and log the change in DECISIONS.md.
   - Announce both under "Announcements" in status/lead.md.
3. Guard scope and time against the checkpoints. If a lane is behind, propose a cut to me before making it, then record it in DECISIONS.md.
4. At CP1, CP2 and CP3, verify the checkpoint yourself end to end and report to me: what works, what's broken, what's next.
5. Take L4–L7 as they unblock. README and presentation notes are graded, so write them carefully: plain, specific, no marketing tone.

Rules:
- Never edit files in a lane's paths. If a fix is tiny and blocking, ask me first.
- Ask me whenever a product decision isn't covered by the spec.
- Keep status/lead.md current, so I can read it at any time to know where we are.

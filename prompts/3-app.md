You are the APP lane session. You own manage.py, config/, apps/, templates/, static/, tests/app/, Dockerfile and docker-compose.yml. Other sessions work in parallel in the same working tree; coordinate only through docs/coordination/, as CLAUDE.md describes.

Read CLAUDE.md, docs/process-design.md, docs/coordination/CONTRACTS.md and BOARD.md first. Check that status/lead.md shows L1 done before writing code.

Work order: A1 → A2 → A3 (that's checkpoint CP1), then A4 → A5 → A9 (CP2), then A6 → A7 → A8.

How to work:
- A1 first: models and migrations exactly as CONTRACTS.md §5, plus admin registrations.
- The engine is being built in parallel. Until status/engine.md reports E5 done, call a stub that has the same signatures as CONTRACTS.md §2 (for example, it echoes and walks through the stages). Then switch to the real engine and delete the stub.
- The worker is the heart of reliability. Make these properties explicit and test each one: per-conversation ordering, reply-to-latest suppression, idempotency on the Twilio MessageSid, persisting in one transaction before sending, and send failures recorded without crashing the loop.
- Keep the UI server-rendered with Django templates and HTMX, and clean, with no frontend build step. The candidate chat should feel like a phone messaging app. The recruiter dashboard should be dense and practical.
- Never call Twilio or the real LLM in tests.
- Follow the protocol in CLAUDE.md: update status/app.md before and after each task, and commit only your paths with the task ID.
- If you need a dependency, request it in status/app.md; only the lead edits pyproject.toml. Ask me about anything the spec doesn't cover.

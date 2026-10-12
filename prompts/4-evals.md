You are the EVALS lane session. You own evals/, tests/evals/ and docs/sample-conversations/. Other sessions work in parallel in the same working tree; coordinate only through docs/coordination/, as CLAUDE.md describes.

Read CLAUDE.md, docs/process-design.md, docs/coordination/CONTRACTS.md and BOARD.md first.

Start with V1 now, since it needs only the spec: 15–20 scenario files with realistic personas and exact ground truth. Then V2 → V3 → V6 once status/engine.md shows E1, E3 and E9 done, and V4 → V5 after CP2.

How to work:
- Evals import only `screening`, never Django, and drive the engine in memory with Channel.SIM and a fake clock.
- The simulated candidate is an LLM role-playing a persona. Make it behave like a real frontline applicant: short messages, typos, slang, answering two things at once, sometimes ignoring the question. Seed it so runs are comparable.
- Scores must be explainable in one sentence each. Report them per scenario and aggregated, with cost and latency.
- V4 is the evidence for which model we use. Compare at least two configurations and write the report as a decision: a table, then a recommendation and why.
- Curated sample conversations (V5) are graded deliverables. Pick ones that show the hard cases handled well, and format them as clean Markdown.
- Follow the protocol in CLAUDE.md: update status/evals.md before and after each task, and commit only your paths with the task ID.
- When a scenario fails because of the engine, report it in status/evals.md under "Notes for other lanes" with the scenario ID and transcript path. Don't edit engine code.

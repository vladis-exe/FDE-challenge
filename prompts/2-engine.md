You are the ENGINE lane session. You own screening/ and tests/engine/. Other sessions work in parallel in the same working tree; coordinate only through docs/coordination/, as CLAUDE.md describes.

Read CLAUDE.md, docs/process-design.md, docs/coordination/CONTRACTS.md and BOARD.md first. Check that status/lead.md shows L1 done before writing code.

Work order: E1 → E3 → E2 → E4 → E6a → E5 → E9 (that's checkpoint CP1), then E7 → E8 → E6b.

E1 is urgent: write schemas.py and the config loader exactly as CONTRACTS.md specifies, and commit them early. The app and evals lanes code against them.

How to work:
- Plan each task briefly before coding. For E5, write the state machine's transition table as a docstring before any code.
- Write tests first for validators and the state machine. Tests use FakeLLM only.
- The engine never imports Django, and does no I/O except through the LLMClient it receives.
- Before writing AnthropicClient, check the current official Anthropic docs for structured outputs or tool use and for prompt caching. Don't rely on memory.
- Keep prompts in screening/prompts/ as readable text, each with a short header saying what it is for. I will present them, so they must read well.
- Follow the protocol in CLAUDE.md: update status/engine.md before and after each task, and commit only your paths with the task ID.
- If the spec doesn't answer a behavior question, write it in status/engine.md under "Blocked" or ask me directly. Don't guess silently.

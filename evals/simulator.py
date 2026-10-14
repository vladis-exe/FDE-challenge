"""Drive the engine with a simulated candidate on a fake clock.

The candidate is an LLM role-playing the scenario's persona. Everything that must be
the same from run to run is decided in code instead: scripted turns fire on a turn
number or stage, pauses tick the fake clock through reminders and quiet hours, and a
seeded RNG picks typing delays and the occasional style quirk. No sampling seed exists
on current models, so this is what makes two runs comparable.

Reply-to-latest (CONTRACTS §5) is the app's job; a burst here applies it the same way:
every message updates state, and only the last one's replies are delivered.
"""

import random
import time
from datetime import datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from evals.scenario import Pause, Scenario, ScriptedTurn
from screening import engine
from screening.engine import EngineContext
from screening.llm import LLMClient, LLMError
from screening.record import final_record
from screening.schemas import (
    Channel,
    ConversationState,
    Event,
    InboundMessage,
    Status,
    TurnResult,
)

AFTER_CLOSE_WATCH = timedelta(hours=25)  # keep ticking after the end: nothing more may be sent
QUIRK_ODDS = 0.35
QUIRKS = [
    "Include one realistic typo.",
    "No capital letters and no punctuation at all this time.",
    "Answer in as few words as you can.",
    "If it fits naturally, also mention one more fact Alex hasn't asked about yet.",
]
SIDETRACK = (
    "This time don't answer yet: reply with a short reaction or a quick question of your own "
    "(about the job or the process), as people sometimes do."
)


class Line(BaseModel):
    """One message in the eval transcript."""

    role: Literal["candidate", "agent"]
    at: datetime
    text: str
    kind: str = "message"  # agent lines: reply, reminder or close
    media: str = "none"
    suppressed: bool = False  # an agent reply dropped by reply-to-latest
    stage_before: str = ""  # candidate lines: the engine stage the message answered
    stage_after: str = ""
    events: list[str] = []  # candidate lines: event types the turn produced
    latency_ms: int | None = None  # candidate lines: wall-clock time of handle_message
    scripted: bool = False


class SimResult(BaseModel):
    scenario_id: str
    lines: list[Line]
    events: list[Event]
    state: ConversationState
    record: dict
    candidate_turns: int
    hit_max_turns: bool = False
    error: str | None = None
    simulator_tokens: dict[str, int] = {"input": 0, "output": 0}


class Candidate(Protocol):
    tokens: dict[str, int]

    def reply(self, lines: list[Line], directive: str | None, stage: str, now: datetime) -> str: ...


class Persona:
    """The simulated candidate: one LLM call per free-form message."""

    def __init__(self, scenario: Scenario, llm: LLMClient) -> None:
        self.llm = llm
        self.system = persona_prompt(scenario)
        self.tokens = {"input": 0, "output": 0}

    def reply(self, lines: list[Line], directive: str | None, stage: str, now: datetime) -> str:
        messages = as_chat(lines)
        # A real candidate knows today's date, which they need to check a read-back date.
        note = f"It is {now:%A %d %B %Y, %H:%M} where you are."
        if directive:
            note += f" Director's note, this message only: {directive}"
        messages[-1]["content"] += f"\n\n[{note}]"
        result = self.llm.text(
            purpose="simulate", system=self.system, messages=messages, tier="smart", max_tokens=150
        )
        self.tokens["input"] += result.usage.input_tokens
        self.tokens["output"] += result.usage.output_tokens
        return clean(result.value)


def persona_prompt(scenario: Scenario) -> str:
    facts = "\n".join(f"- {key}: {value}" for key, value in scenario.facts.items())
    behaviors = "\n".join(f"- {b}" for b in scenario.behaviors)
    language = {"es": "Spanish", "en": "English"}[scenario.language]
    country = {"ES": "Spain", "MX": "Mexico"}[scenario.country]
    return f"""You play a job applicant chatting on WhatsApp with Alex, the AI hiring assistant \
of Grupo Sazón, which hires delivery drivers. This is a test of Alex, so be a realistic \
applicant, not a helpful one.

Who you are:
{scenario.persona.strip()}

What you know. These are the only facts you may give; never invent other details. If asked \
something they don't cover, say you're not sure.
{facts}

How you write:
{behaviors}
- Like real frontline applicants in {country}: short messages (usually 1 to 10 words), casual, \
local slang, few accents or capitals, the odd typo. Never write like a form, never use lists.
- Write in {language} unless the notes above say otherwise.

Rules:
- Reply with the text of your next WhatsApp message only: no quotes, no narration, no notes.
- Answer what Alex asks from your facts, one message at a time.
- When Alex reads back your answers, check them against your facts and correct anything wrong.
- Never say you are an AI, a test or a simulation."""


def as_chat(lines: list[Line]) -> list[dict[str, str]]:
    """The transcript from the candidate's side: Alex is the user, the candidate the assistant."""
    messages: list[dict[str, str]] = []
    for line in lines:
        if line.suppressed:
            continue  # never delivered, so the candidate never saw it
        role = "user" if line.role == "agent" else "assistant"
        text = line.text or f"[you sent a {line.media} message]"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + text
        else:
            messages.append({"role": role, "content": text})
    return messages


def clean(text: str) -> str:
    text = text.strip().strip('"“”').strip()
    return " ".join(text.split())[:400]


class Simulation:
    def __init__(self, scenario: Scenario, ctx: EngineContext, persona: Candidate) -> None:
        self.scenario = scenario
        self.ctx = ctx
        self.persona = persona
        self.rng = random.Random(scenario.seed)
        self.clock = scenario.starts_at
        self.lines: list[Line] = []
        self.events: list[Event] = []
        self.used_script: set[int] = set()
        self.used_pauses: set[int] = set()
        self.sidetracked = False
        self.message_count = 0
        self.state = engine.new_conversation(
            f"eval-{scenario.id}",
            Channel.SIM,
            phone=scenario.phone,
            language=scenario.language,
            now=self.clock,
        )

    def run(self) -> SimResult:
        self._apply(engine.start(self.state, now=self.clock, ctx=self.ctx), self.clock)
        turns = 0
        error = None
        try:
            while self.state.status is Status.IN_PROGRESS and turns < self.scenario.max_turns:
                pause = self._pause()
                if pause is not None:
                    self._tick_until(self.clock + pause.duration)
                    if not pause.resume or self.state.status is not Status.IN_PROGRESS:
                        break
                turns += 1
                self._candidate_turn(turns)
        except LLMError as exc:  # the simulator's own LLM failed; the engine never raises
            error = f"simulator: {exc}"
        stuck = self.state.status is Status.IN_PROGRESS and error is None
        if not stuck:
            self._tick_until(self.clock + AFTER_CLOSE_WATCH)
        return SimResult(
            scenario_id=self.scenario.id,
            lines=self.lines,
            events=self.events,
            state=self.state,
            record=final_record(self.state),
            candidate_turns=turns,
            hit_max_turns=stuck,
            error=error,
            simulator_tokens=self.persona.tokens,
        )

    def _candidate_turn(self, turn: int) -> None:
        script = self._script(turn)
        self._wait(self.rng.uniform(15, 75))
        if script is not None:
            self._send(script.text, script.media, scripted=True, last=not script.burst)
            for i, text in enumerate(script.burst):
                self._wait(self.rng.uniform(3, 10))
                self._send(text, "none", scripted=True, last=i == len(script.burst) - 1)
            return
        directive = self._directive()
        local = self.clock.astimezone(ZoneInfo(self.ctx.config.timezone_for(self.scenario.country)))
        self._send(self.persona.reply(self.lines, directive, self.state.stage.value, local), "none")

    def _directive(self) -> str | None:
        if self.state.stage.value == "confirm" or self.rng.random() >= QUIRK_ODDS:
            return None
        # Ignoring the question costs the engine a re-ask; once per run keeps the
        # ground truth reachable (two would risk flagging a field the persona knows).
        if not self.sidetracked and self.rng.random() < 0.25:
            self.sidetracked = True
            return SIDETRACK
        return self.rng.choice(QUIRKS)

    def _send(self, text: str, media: str, *, scripted: bool = False, last: bool = True) -> None:
        self.message_count += 1
        message = InboundMessage(
            id=f"m{self.message_count}",
            text=text,
            received_at=self.clock,
            media=media,  # type: ignore[arg-type]
        )
        stage_before = self.state.stage.value
        started = time.monotonic()
        result = engine.handle_message(self.state, message, ctx=self.ctx)
        latency = round((time.monotonic() - started) * 1000)
        self.lines.append(
            Line(
                role="candidate",
                at=self.clock,
                text=text,
                media=media,
                stage_before=stage_before,
                stage_after=result.state.stage.value,
                events=[e.type for e in result.events],
                latency_ms=latency,
                scripted=scripted,
            )
        )
        self._apply(result, self.clock, deliver=last)

    def _apply(self, result: TurnResult, at: datetime, *, deliver: bool = True) -> None:
        self.state = result.state
        self.events.extend(result.events)
        for out in result.outbound:
            suppressed = not deliver and out.kind != "close"  # closes are never dropped
            self.lines.append(
                Line(role="agent", at=at, text=out.text, kind=out.kind, suppressed=suppressed)
            )

    def _tick_until(self, end: datetime) -> None:
        while True:
            due = engine.next_due_at(self.state, config=self.ctx.config)
            if due is None or due > end:
                break
            self.clock = max(self.clock, due)
            result = engine.handle_tick(self.state, now=self.clock, ctx=self.ctx)
            if not result.changed:
                break
            self._apply(result, self.clock)
        self.clock = max(self.clock, end)

    def _wait(self, seconds: float) -> None:
        self.clock += timedelta(seconds=round(seconds))

    def _script(self, turn: int) -> ScriptedTurn | None:
        for i, item in enumerate(self.scenario.script):
            if i in self.used_script:
                continue
            if item.when.turn == turn or item.when.stage == self.state.stage.value:
                self.used_script.add(i)
                return item
        return None

    def _pause(self) -> Pause | None:
        for i, pause in enumerate(self.scenario.pauses):
            if i not in self.used_pauses and pause.at_stage == self.state.stage.value:
                self.used_pauses.add(i)
                return pause
        return None


def simulate(scenario: Scenario, ctx: EngineContext, candidate: Candidate) -> SimResult:
    return Simulation(scenario, ctx, candidate).run()

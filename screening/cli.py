"""Talk to the screening engine in the terminal.

    uv run python -m screening.cli [--lang es|en] [--country ES|MX] [--fake] [--script file.txt]

Each turn prints Alex's replies, what changed in the state, and the events.
--script reads one candidate message per line ("#" starts a comment, "[audio]"
sends a voice note). --fake swaps the LLM for a keyword stub, so the CLI runs
without an API key; it only understands direct answers to the current question.
"""

import argparse
import re
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from screening import engine
from screening.config import load_config
from screening.llm import AnthropicClient, FakeLLM, LLMClient
from screening.schemas import Channel, ConversationState, InboundMessage, Status, TurnResult

DIM, BOLD, CYAN = "2", "1", "1;36"


def style(text: str, code: str) -> str:
    """ANSI styling for a terminal; plain text when piped to a file or captured."""
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m screening.cli", description=__doc__.split("\n")[0]
    )
    parser.add_argument("--lang", choices=["es", "en"], default="es")
    parser.add_argument("--country", choices=["ES", "MX"], default="ES")
    parser.add_argument("--fake", action="store_true", help="keyword stub instead of the real LLM")
    parser.add_argument("--script", type=Path, help="file with one candidate message per line")
    args = parser.parse_args(argv)

    load_dotenv()
    llm: LLMClient = fake_llm() if args.fake else AnthropicClient()
    ctx = engine.EngineContext(config=load_config(), llm=llm)
    now = datetime.now(UTC)

    state = engine.new_conversation("cli", Channel.SIM, phone=None, language=args.lang, now=now)
    state.country_hint = args.country  # what the web chat's country picker does
    result = engine.start(state, now=now, ctx=ctx)
    show(state, result)
    state = result.state

    lines = script_lines(args.script) if args.script else interactive_lines()
    for number, text in enumerate(lines, start=1):
        if state.status not in (Status.IN_PROGRESS, Status.ABANDONED):
            break
        media = "audio" if text == "[audio]" else "none"
        # Scripted turns are a minute apart so timestamps read naturally.
        now = now + timedelta(minutes=1) if args.script else datetime.now(UTC)
        message = InboundMessage(
            id=f"m{number}", text="" if media != "none" else text, received_at=now, media=media
        )
        print(f"\n{style('Candidate:', BOLD)} {text}")
        result = engine.handle_message(state, message, ctx=ctx)
        show(state, result)
        state = result.state

    print(f"\n{style('Final status:', BOLD)} {state.status.value}", end="")
    if state.disqualify_reason:
        print(f" ({state.disqualify_reason})", end="")
    if state.review_reasons:
        print(f" (review: {', '.join(state.review_reasons)})", end="")
    print()
    return 0


def show(before: ConversationState, result: TurnResult) -> None:
    for message in result.outbound:
        print(f"{style(f'Alex [{message.kind}]:', CYAN)} {message.text}")
    for path, (old, new) in diff(before, result.state).items():
        print(style(f"  state {path}: {old!r} -> {new!r}", DIM))
    for event in result.events:
        print(style(f"  event {format_event(event.type, event.data)}", DIM))


def diff(before: ConversationState, after: ConversationState) -> dict[str, tuple[Any, Any]]:
    """Changed leaf values as dotted paths, leaving out the transcript and timestamps."""
    skip = {"transcript_tail", "last_inbound_at", "last_outbound_at"}
    old = flatten({k: v for k, v in before.model_dump(mode="json").items() if k not in skip})
    new = flatten({k: v for k, v in after.model_dump(mode="json").items() if k not in skip})
    return {path: (old.get(path), new.get(path)) for path in new if old.get(path) != new[path]}


def flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(data, dict) and data:
        flat: dict[str, Any] = {}
        for key, value in data.items():
            flat.update(flatten(value, f"{prefix}.{key}" if prefix else key))
        return flat
    return {prefix: data}


def format_event(type_: str, data: dict[str, Any]) -> str:
    if type_ == "llm_call":
        return (
            f"llm_call {data['purpose']} {data['model']} in={data['input_tokens']} "
            f"(cached {data.get('cache_read_tokens', 0)}) out={data['output_tokens']} "
            f"{data['latency_ms']}ms"
        )
    details = " ".join(f"{key}={value}" for key, value in data.items())
    return f"{type_} {details}".strip()


def script_lines(path: Path) -> Iterator[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            yield line


def interactive_lines() -> Iterator[str]:
    print(style("(type the candidate's messages; empty line or Ctrl-D to stop)", DIM))
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            return
        if not line:
            return
        yield line


# --fake: a keyword stub that answers whatever field is being asked.

YES = {"si", "sí", "yes", "claro", "vale", "ok", "👍"}
NO = {"no", "nope", "nel", "👎"}
AVAILABILITY_WORDS = {
    "complet": "full_time",
    "full": "full_time",
    "media": "part_time",
    "medio": "part_time",
    "part": "part_time",
    "fin": "weekends",
    "weekend": "weekends",
}
SCHEDULE_WORDS = {
    "mañana": "morning",
    "morning": "morning",
    "tarde": "afternoon",
    "afternoon": "afternoon",
    "noche": "evening",
    "evening": "evening",
    "flex": "flexible",
}


def fake_llm() -> FakeLLM:
    return FakeLLM({"extract": fake_extract, "compose": fake_compose})


def fake_extract(system: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    prompt = messages[-1]["content"]
    asking = re.search(r"Asking for: (.+)", prompt).group(1)
    text = prompt.split("<candidate_message>\n")[1].split("\n</candidate_message>")[0].strip()
    lowered = text.lower().strip(" .!¡¿?")
    yes, no = lowered in YES, lowered in NO
    english = re.search(r"\b(yes|i|my|the)\b", lowered) is not None
    record: dict[str, Any] = {"intent": "answer", "language": "en" if english else "es"}
    fields: dict[str, Any] = {}

    if asking == "consent":
        record["consent"] = "no" if no else "yes"
    elif asking == "full name":
        fields["full_name"] = text
    elif asking == "license":
        fields["license"] = "yes" if yes else "no" if no else "vague"
    elif asking.startswith("confirmation of") and (yes or no):
        record["confirmation"] = "confirm" if yes else "deny"
    elif asking == "city" or asking.startswith("confirmation of"):
        fields["city_text"] = text
    elif asking == "availability":
        fields["availability"] = [v for k, v in AVAILABILITY_WORDS.items() if k in lowered]
    elif asking == "schedule":
        fields["schedule"] = [v for k, v in SCHEDULE_WORDS.items() if k in lowered]
    elif asking == "experience":
        years = re.search(r"\d+(?:[.,]\d+)?", lowered)
        if no or not years:
            fields["has_experience"] = False
        else:
            amount = float(years.group().replace(",", "."))
            fields["experience"] = [{"platform": lowered.split()[0], "years": amount}]
    elif asking == "start date":
        fields["start_date"] = {"kind": "asap"}
    elif asking.startswith("confirm"):
        record["confirmation"] = "confirm" if yes else "deny"
    record["fields"] = fields
    return record


def fake_compose(system: str, messages: list[dict[str, str]]) -> str:
    plan = messages[-1]["content"].split("<write>\n")[1].split("\n</write>")[0]
    return "[fake compose] " + " ".join(plan.splitlines())


if __name__ == "__main__":
    sys.exit(main())

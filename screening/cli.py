"""Talk to the screening engine in the terminal.

    uv run python -m screening.cli [--vacancy ID] [--lang es|en] [--country ES|MX] [--fake]
                                   [--script file.txt]

Each turn prints Alex's replies, what changed in the state, and the events.
--script reads one candidate message per line ("#" starts a comment, "[audio]"
sends a voice note). --fake swaps the LLM for a keyword stub, so the CLI runs
without an API key; it only understands direct answers to the current question.
"""

import argparse
import json
import re
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from screening import engine
from screening.config import VacancyConfig, load_config
from screening.llm import AnthropicClient, FakeLLM, LLMClient
from screening.record import final_record
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
    parser.add_argument("--vacancy", default="driver", help="a file name in config/vacancies/")
    parser.add_argument("--country", choices=["ES", "MX"], default="ES")
    parser.add_argument("--fake", action="store_true", help="keyword stub instead of the real LLM")
    parser.add_argument("--script", type=Path, help="file with one candidate message per line")
    args = parser.parse_args(argv)

    load_dotenv()
    config = load_config()
    if args.vacancy not in config.vacancies:
        parser.error(f"unknown vacancy {args.vacancy!r}; choose from {', '.join(config.vacancies)}")
    llm: LLMClient = fake_llm(config.vacancy(args.vacancy)) if args.fake else AnthropicClient()
    ctx = engine.EngineContext(config=config, llm=llm)
    now = datetime.now(UTC)

    state = engine.new_conversation(
        "cli", Channel.SIM, vacancy_id=args.vacancy, phone=None, language=args.lang, now=now
    )
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
    if state.status not in (Status.IN_PROGRESS, Status.ABANDONED):
        print(style("Final record:", BOLD))
        print(json.dumps(final_record(state), ensure_ascii=False, indent=2))
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


# --fake: a keyword stub that answers whatever field is being asked, by field type.

YES = {"si", "sí", "yes", "claro", "vale", "ok", "👍"}
NO = {"no", "nope", "nel", "👎"}
OPTION_WORDS = {
    "complet": "full_time",
    "full": "full_time",
    "media": "part_time",
    "medio": "part_time",
    "part": "part_time",
    "fin": "weekends",
    "weekend": "weekends",
    "mañana": "morning",
    "morning": "morning",
    "tarde": "afternoon",
    "afternoon": "afternoon",
    "noche": "evening",
    "evening": "evening",
    "flex": "flexible",
}


def fake_llm(vacancy: VacancyConfig) -> FakeLLM:
    return FakeLLM(
        {
            "extract": lambda system, messages: fake_extract(vacancy, messages),
            "compose": fake_compose,
            "summary": lambda system, messages: "[fake summary]",
        }
    )


def fake_extract(vacancy: VacancyConfig, messages: list[dict[str, str]]) -> dict[str, Any]:
    prompt = messages[-1]["content"]
    asking = re.search(r"Asking for: (.+)", prompt).group(1)
    text = prompt.split("<candidate_message>\n")[1].split("\n</candidate_message>")[0].strip()
    lowered = text.lower().strip(" .!¡¿?")
    yes, no = lowered in YES, lowered in NO
    english = re.search(r"\b(yes|i|my|the)\b", lowered) is not None
    record: dict[str, Any] = {"intent": "answer", "language": "en" if english else "es"}
    fields: dict[str, Any] = {}
    record["fields"] = fields

    if asking == "consent":
        record["consent"] = "no" if no else "yes"
        return record
    if asking.startswith("confirm"):  # the read-back, or an out-of-area city
        if yes or no:
            record["confirmation"] = "confirm" if yes else "deny"
        else:
            city = next(spec for spec in vacancy.asked if spec.type == "city")
            fields[city.name] = text
        return record
    spec = next((spec for spec in vacancy.asked if asking.startswith(spec.name)), None)
    if spec is None:
        return record
    if spec.type in ("text", "city"):
        fields[spec.name] = text
    elif spec.type == "boolean":
        fields[spec.name] = "yes" if yes else "no" if no else "vague"
    elif spec.type == "enum_multi":
        chosen = {value for word, value in OPTION_WORDS.items() if word in lowered}
        fields[spec.name] = [option for option in spec.options if option in chosen]
    elif spec.type == "experience":
        years = re.search(r"\d+(?:[.,]\d+)?", lowered)
        if no or not years:
            fields[spec.name] = {"has_experience": False}
        else:
            amount = float(years.group().replace(",", "."))
            fields[spec.name] = {"items": [{"platform": lowered.split()[0], "years": amount}]}
    elif spec.type == "date":
        fields[spec.name] = {"kind": "asap"}
    return record


def fake_compose(system: str, messages: list[dict[str, str]]) -> str:
    """The plan as one line that passes the message rules (one sentence, question last)."""
    plan = messages[0]["content"].split("<write>\n")[1].split("\n</write>")[0]
    text = re.sub(r"[.?!¿¡]", "", "; ".join(plan.splitlines()))
    return f"(fake) {text}" + ("?" if "Ask for:" in plan else ".")


if __name__ == "__main__":
    sys.exit(main())

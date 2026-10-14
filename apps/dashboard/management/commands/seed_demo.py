"""Load demo data: a recruiter login and real screenings from an eval run.

The conversations come from `apps/dashboard/fixtures/demo_conversations.json`, which is built
from an eval run (`--from-run evals/runs/<dir>`): the real engine and LLM talking to simulated
candidates. Every state, record, event and message is the engine's own output; only the
identifiers, phone numbers and timestamps are rewritten.

The fixture must come from an engine at the current state schema (CONTRACTS v4:
`schema_version` 2, fields per vacancy). An older one is refused rather than migrated:
it's demo data, so the fix is a fresh eval run, not a conversion.
"""

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.messaging.models import Event, Message

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "demo_conversations.json"
SPREAD = timedelta(days=7)
# Every fourth demo candidate came through the web chat; the rest applied on WhatsApp.
WEB_EVERY = 4
SCHEMA_VERSION = 2


class Command(BaseCommand):
    help = "Create a recruiter login and demo conversations (empty databases only, or --reset)."

    def add_arguments(self, parser):
        parser.add_argument("--from-run", type=Path, help="Rebuild the fixture from an eval run.")
        parser.add_argument("--fixture", type=Path, default=FIXTURE)
        parser.add_argument(
            "--reset", action="store_true", help="Delete ALL candidates first (demo DBs only)."
        )
        parser.add_argument("--username", default="recruiter")
        parser.add_argument("--password", default=os.environ.get("DEMO_RECRUITER_PASSWORD"))

    def handle(self, *args, from_run, fixture, reset, username, password, **options):
        if from_run:
            count = build_fixture(from_run, fixture)
            self.stdout.write(f"wrote {count} conversations to {fixture}")
            return

        if Conversation.objects.exists() and not reset:
            raise CommandError("the database already has conversations; pass --reset to replace")
        conversations = json.loads(fixture.read_text(encoding="utf-8"))
        old = {item["state"].get("schema_version", 1) for item in conversations} - {SCHEMA_VERSION}
        if old:
            raise CommandError(
                f"{fixture.name} was built from an engine at schema_version {sorted(old)}, "
                f"not {SCHEMA_VERSION}; rebuild it from a current eval run: "
                "seed_demo --from-run evals/runs/<dir>"
            )
        now = timezone.now()
        with transaction.atomic():
            if reset:
                Candidate.objects.all().delete()
            for index, item in enumerate(conversations):
                load_conversation(item, index, len(conversations), now)
            generated = self._recruiter(username, password)

        self.stdout.write(f"seeded {len(conversations)} conversations")
        if generated:
            self.stdout.write(f"recruiter login: {username} / {generated}")
        else:
            self.stdout.write(f"recruiter login: {username} (password as given)")

    def _recruiter(self, username: str, password: str | None) -> str | None:
        """Create or update the recruiter. Returns the password if we generated it."""
        generated = None if password else secrets.token_urlsafe(9)
        user, _ = get_user_model().objects.get_or_create(username=username)
        user.set_password(password or generated)
        user.save()
        return generated


def build_fixture(run_dir: Path, fixture: Path) -> int:
    """Keep what the app needs from each scenario transcript in an eval run."""
    items = []
    for path in sorted(run_dir.glob("[0-9]*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))["run"]
        if run.get("error"):
            continue
        items.append(
            {
                "scenario_id": run["scenario_id"],
                "lines": [
                    {
                        key: line[key]
                        for key in ("role", "at", "text", "kind", "media", "suppressed")
                    }
                    for line in run["lines"]
                ],
                "events": run["events"],
                "state": run["state"],
                "record": run["record"],
            }
        )
    fixture.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(items)


def load_conversation(item: dict, index: int, total: int, now: datetime) -> Conversation:
    lines = item["lines"]
    first = datetime.fromisoformat(lines[0]["at"])
    last = datetime.fromisoformat(lines[-1]["at"])
    # Spread start times over the past week, oldest first, all finished before now.
    target = now - SPREAD * (total - index) / total
    shift = min(target, now - (last - first) - timedelta(minutes=5)) - first

    def moved(at: str) -> datetime:
        return datetime.fromisoformat(at) + shift

    state = item["state"]
    fields = state["profile"]["fields"]
    location = item["record"]["fields"].get("location") or {}
    country = location.get("country") or state["country_hint"]
    web = index % WEB_EVERY == WEB_EVERY - 1
    phone = None if web else _phone(country, index)
    channel = Conversation.Channel.WEB if web else Conversation.Channel.WHATSAPP

    conversation_id = uuid.uuid4()
    candidate = Candidate.objects.create(
        phone=phone, name=item["record"]["fields"].get("full_name") or ""
    )
    conversation = Conversation.objects.create(
        id=conversation_id, candidate=candidate, channel=channel, vacancy_id=state["vacancy_id"]
    )

    messages = Message.objects.bulk_create(
        Message(
            conversation=conversation,
            direction=Message.Direction.IN
            if line["role"] == "candidate"
            else Message.Direction.OUT,
            kind=Message.Kind.INBOUND if line["role"] == "candidate" else line["kind"],
            text=line["text"],
            media=line["media"],
            suppressed=line["suppressed"],
        )
        for line in lines
    )
    for message, line in zip(messages, lines, strict=True):
        message.created_at = moved(line["at"])
        if message.direction == Message.Direction.IN:
            message.processed_at = message.created_at
    Message.objects.bulk_update(messages, ["created_at", "processed_at"])

    # The simulator numbers candidate messages m1, m2, …; point provenance at our rows.
    inbound = [m for m in messages if m.direction == Message.Direction.IN]
    ids = {f"m{n}": str(m.pk) for n, m in enumerate(inbound, start=1)}
    for field in fields.values():
        field["source_message_id"] = ids.get(field["source_message_id"])
    for line in state["transcript_tail"]:
        line["message_id"] = ids.get(line["message_id"])
        line["at"] = moved(line["at"]).isoformat()
    for key in ("consent_at", "last_inbound_at", "last_outbound_at"):
        if state.get(key):
            state[key] = moved(state[key]).isoformat()
    state["conversation_id"] = str(conversation_id)
    state["channel"] = str(channel)

    finished = state["status"] != Conversation.Status.IN_PROGRESS
    Conversation.objects.filter(pk=conversation_id).update(
        state=state,
        status=state["status"],
        stage=state["stage"],
        preference_score=state["preference_score"],
        language=state["language"],
        country=location.get("country") or state["country_hint"] or "",
        city=location.get("city") or "",
        final_record={**item["record"], "conversation_id": str(conversation_id)}
        if finished
        else None,
        summary=state.get("summary") or "",
        started_at=moved(lines[0]["at"]),
        last_inbound_at=state.get("last_inbound_at"),  # already moved above
        completed_at=moved(lines[-1]["at"]) if finished else None,
        next_tick_at=None,
    )
    Event.objects.bulk_create(
        Event(
            conversation=conversation,
            type=event["type"],
            data=event["data"],
            created_at=moved(event["at"]),
        )
        for event in item["events"]
    )
    return conversation


def _phone(country: str, index: int) -> str:
    # Fictional numbers in each country's mobile format.
    return f"+3460000{index:04d}" if country == "ES" else f"+52550000{index:04d}"

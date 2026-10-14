"""Screening analytics for the dashboard: funnel, outcomes, timing, reminders and LLM cost.

Aggregated in Python from a handful of queries: at ~1,000 conversations a week this is a few
thousand rows, and plain Python is easier to read and verify than database-specific SQL.
"""

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Max, Min

from apps.candidates.models import Conversation
from apps.messaging.models import Event, Message
from evals.pricing import call_cost  # TODO: screening.llm.pricing once moved (see status/app.md)
from screening.schemas import Stage

FINISHED = {
    Conversation.Status.QUALIFIED,
    Conversation.Status.NEEDS_REVIEW,
    Conversation.Status.DISQUALIFIED,
}
STAGE_LABELS = {
    Stage.CONSENT: "Started",
    Stage.NAME: "Consented",
    Stage.LICENSE: "Gave name",
    Stage.LOCATION: "License OK",
    Stage.AVAILABILITY: "City OK",
    Stage.SCHEDULE: "Availability",
    Stage.EXPERIENCE: "Schedule",
    Stage.START_DATE: "Experience",
    Stage.CONFIRM: "Start date",
    Stage.DONE: "Confirmed",
}
# Where a candidate stopped: the question they were being asked.
QUESTION_LABELS = {
    Stage.CONSENT: "Consent",
    Stage.NAME: "Name",
    Stage.LICENSE: "License",
    Stage.LOCATION: "City",
    Stage.AVAILABILITY: "Availability",
    Stage.SCHEDULE: "Schedule",
    Stage.EXPERIENCE: "Experience",
    Stage.START_DATE: "Start date",
    Stage.CONFIRM: "Confirmation",
    Stage.DONE: "Done",
}
STAGES = list(Stage)
REASON_LABELS = {
    "no_license": "No driver's license",
    "out_of_area": "City not served",
    "recruiter decision": "Recruiter decision",
}


@dataclass
class Bar:
    label: str
    count: int
    share: float  # 0-1, of the bar chart's base


@dataclass
class LLMUsage:
    purpose: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: list[int] = field(default_factory=list)

    @property
    def median_latency_ms(self) -> int:
        return int(statistics.median(self.latency_ms)) if self.latency_ms else 0


@dataclass
class Report:
    started: int
    finished: int
    qualified: int
    median_time_to_complete: timedelta | None
    reminded: int
    replied_after_reminder: int
    funnel: list[Bar]
    outcomes: list[Bar]
    disqualify_reasons: list[Bar]
    abandoned_at: list[Bar]
    llm: list[LLMUsage]
    llm_cost_total: float

    @property
    def median_time_label(self) -> str:
        if self.median_time_to_complete is None:
            return "—"
        minutes, seconds = divmod(round(self.median_time_to_complete.total_seconds()), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m" if hours else f"{minutes}m {seconds:02d}s"

    @property
    def cost_per_conversation(self) -> float | None:
        return self.llm_cost_total / self.started if self.started else None


def bars(counts: Counter, base: int, labels: dict | None = None) -> list[Bar]:
    return [
        Bar((labels or {}).get(key, key), count, count / base if base else 0)
        for key, count in counts.most_common()
    ]


def build(since: datetime | None = None) -> Report:
    conversations = Conversation.objects.all()
    if since:
        conversations = conversations.filter(started_at__gte=since)
    rows = list(
        conversations.values("id", "status", "stage", "started_at", "completed_at", "final_record")
    )
    ids = [row["id"] for row in rows]
    started = len(rows)

    # Funnel: a conversation reached every stage up to its current one.
    reached = Counter()
    for row in rows:
        index = STAGES.index(Stage(row["stage"])) if row["stage"] else 0
        for stage in STAGES[: index + 1]:
            reached[stage] += 1
    funnel = [
        Bar(STAGE_LABELS[stage], reached[stage], reached[stage] / started if started else 0)
        for stage in STAGES
    ]

    statuses = Counter(row["status"] for row in rows)
    status_labels = dict(Conversation.Status.choices)
    finished_rows = [row for row in rows if row["status"] in FINISHED]
    durations = [
        row["completed_at"] - row["started_at"] for row in finished_rows if row["completed_at"]
    ]
    reasons = Counter(
        row["final_record"]["disqualify_reason"] or "recruiter decision"
        for row in rows
        if row["status"] == Conversation.Status.DISQUALIFIED and row["final_record"]
    )
    abandoned = Counter(
        QUESTION_LABELS[Stage(row["stage"])]
        for row in rows
        if row["status"] == Conversation.Status.ABANDONED and row["stage"]
    )

    # Re-engagement: an inbound message after the first reminder.
    first_reminder = dict(
        Event.objects.filter(conversation_id__in=ids, type="reminder_sent")
        .values("conversation_id")
        .annotate(at=Min("created_at"))
        .values_list("conversation_id", "at")
    )
    last_inbound = dict(
        Message.objects.filter(conversation_id__in=first_reminder, direction=Message.Direction.IN)
        .values("conversation_id")
        .annotate(at=Max("created_at"))
        .values_list("conversation_id", "at")
    )
    replied = sum(
        1 for cid, at in first_reminder.items() if cid in last_inbound and last_inbound[cid] > at
    )

    usage: dict[str, LLMUsage] = {}
    for data in Event.objects.filter(conversation_id__in=ids, type="llm_call").values_list(
        "data", flat=True
    ):
        line = usage.setdefault(data.get("purpose", "?"), LLMUsage(data.get("purpose", "?")))
        line.calls += 1
        line.input_tokens += data.get("input_tokens", 0)
        line.output_tokens += data.get("output_tokens", 0)
        line.cost += call_cost(data)
        line.latency_ms.append(data.get("latency_ms", 0))

    return Report(
        started=started,
        finished=len(finished_rows),
        qualified=statuses[Conversation.Status.QUALIFIED],
        median_time_to_complete=statistics.median(durations) if durations else None,
        reminded=len(first_reminder),
        replied_after_reminder=replied,
        funnel=funnel,
        outcomes=bars(statuses, started, status_labels),
        disqualify_reasons=bars(reasons, sum(reasons.values()), REASON_LABELS),
        abandoned_at=bars(abandoned, sum(abandoned.values())),
        llm=sorted(usage.values(), key=lambda line: line.cost, reverse=True),
        llm_cost_total=sum(line.cost for line in usage.values()),
    )

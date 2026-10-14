from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.dashboard import analytics
from apps.messaging.models import Event, Message

NOW = timezone.now()


DRIVER_FIELDS = [
    "full_name", "has_driver_license", "location", "availability", "schedule", "experience",
    "start_date",
]  # fmt: skip


def conversation(
    status: str,
    stage: str,
    *,
    answered: int = 0,
    field: str | None = None,
    minutes: float | None = None,
    reason=None,
    vacancy: str = "driver",
    read_back: bool = False,
):
    """`answered`: how many of the driver fields, in asking order, the candidate answered."""
    fields = {name: {"status": "accepted"} for name in DRIVER_FIELDS[:answered]}
    c = Conversation.objects.create(
        candidate=Candidate.objects.create(),
        channel="web",
        vacancy_id=vacancy,
        status=status,
        stage=stage,
        state={
            "consent_at": NOW.isoformat() if stage != "consent" else None,
            "current_field": field,
            "profile": {"fields": fields},
        },
        final_record={"disqualify_reason": reason} if status != "in_progress" else None,
    )
    if read_back:
        Event.objects.create(
            conversation=c, type="stage_entered", created_at=NOW, data={"stage": "confirm"}
        )
    if minutes is not None:
        Conversation.objects.filter(pk=c.pk).update(
            started_at=NOW - timedelta(minutes=minutes), completed_at=NOW
        )
    return c


def llm_call(c: Conversation, purpose: str, model="claude-haiku-5-5", tokens=(1000, 100)):
    Event.objects.create(
        conversation=c,
        type="llm_call",
        created_at=NOW,
        data={
            "purpose": purpose,
            "model": model,
            "input_tokens": tokens[0],
            "output_tokens": tokens[1],
            "latency_ms": 800,
        },
    )


@pytest.fixture
def data(db):
    q1 = conversation("qualified", "done", answered=7, read_back=True, minutes=3)
    conversation("qualified", "done", answered=7, read_back=True, minutes=5)
    conversation("needs_review", "done", answered=7, read_back=True, minutes=10)
    conversation("disqualified", "done", answered=2, minutes=1, reason="no_license")
    conversation("disqualified", "done", answered=3, minutes=2, reason="out_of_area")
    a1 = conversation("abandoned", "collecting", answered=2, field="location")
    a2 = conversation("abandoned", "consent")
    back = conversation("in_progress", "collecting", answered=4, field="schedule")
    conversation("qualified", "done", vacancy="kitchen_prep", minutes=4)

    # Re-engagement: `back` replied after its reminder, `a1` and `a2` never did.
    for c in (a1, a2, back):
        Event.objects.create(
            conversation=c, type="reminder_sent", created_at=NOW - timedelta(hours=1)
        )
    Message.objects.create(conversation=a1, direction="in", kind="inbound", text="hola")
    Message.objects.filter(conversation=a1).update(created_at=NOW - timedelta(hours=2))
    Message.objects.create(conversation=back, direction="in", kind="inbound", text="sigo aquí")

    llm_call(q1, "extract")
    llm_call(q1, "compose")
    llm_call(q1, "summary", model="claude-sonnet-5-5", tokens=(2000, 200))


def by_label(bars) -> dict[str, int]:
    return {bar.label: bar.count for bar in bars}


def test_headline_numbers(data):
    report = analytics.build(vacancy_id="driver")
    assert (report.started, report.finished, report.qualified) == (8, 5, 2)
    assert report.median_time_to_complete == timedelta(minutes=3)  # of 1, 2, 3, 5, 10
    assert report.median_time_label == "3m 00s"
    assert (report.reminded, report.replied_after_reminder) == (3, 1)


def test_funnel_for_one_job_has_a_step_per_required_question(data):
    funnel = by_label(analytics.build(vacancy_id="driver").funnel)
    assert list(funnel) == [
        "Started", "Consented", "Answered: name", "Answered: driver license", "Answered: city",
        "Answered: availability", "Answered: schedule", "Answered: experience",
        "Answered: start date", "Reached the read-back", "Finished",
    ]  # fmt: skip
    assert funnel["Started"] == 8 and funnel["Consented"] == 7  # a2 never consented
    assert funnel["Answered: driver license"] == 7  # everyone who consented
    assert funnel["Answered: city"] == 5  # the license knockout and a1 stopped before it
    assert funnel["Answered: schedule"] == 3
    assert (funnel["Reached the read-back"], funnel["Finished"]) == (3, 5)


def test_funnel_across_jobs_shows_only_the_shared_phases(data):
    report = analytics.build()
    assert list(by_label(report.funnel)) == [
        "Started", "Consented", "Reached the read-back", "Finished",
    ]  # fmt: skip
    assert by_label(report.jobs) == {"Delivery driver": 8, "Kitchen prep assistant": 1}


def test_outcomes_reasons_and_drop_off(data):
    report = analytics.build(vacancy_id="driver")
    assert by_label(report.outcomes) == {
        "Qualified": 2, "Disqualified": 2, "Abandoned": 2, "Needs Review": 1, "In Progress": 1,
    }  # fmt: skip
    assert by_label(report.disqualify_reasons) == {"No driver's license": 1, "City not served": 1}
    assert by_label(report.abandoned_at) == {"City": 1, "Consent": 1}


def test_reasons_for_a_new_jobs_knockout_are_named_from_the_field():
    assert analytics.reason_label("no_food_handler_certificate") == "No food handler certificate"


def test_llm_usage_and_cost(data):
    report = analytics.build()
    usage = {line.purpose: line for line in report.llm}
    assert usage["summary"].calls == 1 and usage["extract"].input_tokens == 1000
    # haiku: 2 × (1000 × 0.10 + 100 × 0.50) / 1e6; sonnet: (2000 × 2 + 200 × 10) / 1e6
    assert report.llm_cost_total == pytest.approx(2 * 0.00015 + 0.006)
    assert report.cost_per_conversation == pytest.approx(report.llm_cost_total / 9)
    assert report.llm[0].purpose == "summary"  # most expensive first


def test_period_excludes_older_conversations(data):
    Conversation.objects.filter(status="abandoned").update(started_at=NOW - timedelta(days=40))
    assert analytics.build(since=NOW - timedelta(days=30)).started == 7


def test_empty_database(db):
    report = analytics.build()
    assert report.started == 0 and report.median_time_label == "—"
    assert report.cost_per_conversation is None


def test_analytics_page_requires_login_and_renders(client, data, django_user_model):
    assert client.get(reverse("dashboard_analytics")).status_code == 302
    client.force_login(django_user_model.objects.create_user("r", password="pw-for-tests-only"))
    body = client.get(
        reverse("dashboard_analytics"), {"period": "all", "job": "driver"}
    ).content.decode()
    assert "Screening analytics" in body
    assert "3m 00s" in body and "No driver&#x27;s license" in body
    assert "<code>summary</code>" in body
    assert "1,000" in body  # token counts get thousands separators
    assert "Answered: driver license" in body
    assert '<option value="driver" selected>' in body

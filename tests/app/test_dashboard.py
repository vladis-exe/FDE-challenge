import csv
import io
from datetime import date

import pytest
from django.urls import reverse

from apps.candidates.models import Candidate, Conversation, ReviewAction
from apps.messaging import services
from apps.messaging.models import Event, Message
from screening.record import final_record
from screening.schemas import (
    Availability,
    Channel,
    ConversationState,
    FieldStatus,
    FieldValue,
    Location,
    Schedule,
    Status,
)

ACCEPTED = FieldStatus.ACCEPTED


def make_conversation(
    name: str,
    status: Status = Status.QUALIFIED,
    *,
    phone: str | None = None,
    city: str = "barcelona",
    country: str = "ES",
    availability: tuple[Availability, ...] = (Availability.PART_TIME,),
    schedule: tuple[Schedule, ...] = (Schedule.EVENING,),
    flag_license: bool = False,
) -> Conversation:
    conversation = Conversation.objects.create(
        candidate=Candidate.objects.create(name=name, phone=phone),
        channel=Conversation.Channel.WHATSAPP if phone else Conversation.Channel.WEB,
    )
    state = ConversationState(
        conversation_id=str(conversation.pk), channel=Channel.WEB, status=status
    )
    profile = state.profile
    profile.full_name = FieldValue[str](value=name, status=ACCEPTED, source_message_id="1")
    profile.has_driver_license = (
        FieldValue[bool](status=FieldStatus.FLAGGED, note="license expired")
        if flag_license
        else FieldValue[bool](value=True, status=ACCEPTED)
    )
    profile.location = FieldValue[Location](
        value=Location(country=country, city=city), status=ACCEPTED
    )
    profile.availability = FieldValue[list[Availability]](value=list(availability), status=ACCEPTED)
    profile.schedule = FieldValue[list[Schedule]](value=list(schedule), status=ACCEPTED)
    profile.start_date = FieldValue[date](value=date(2026, 10, 19), status=ACCEPTED)
    if flag_license:
        state.review_reasons = ["license_unclear"]
    state.summary = f"{name} summary."
    conversation.state = state.model_dump(mode="json")
    conversation.status = status
    conversation.country, conversation.city = country, city
    conversation.summary = state.summary
    conversation.final_record = None if status == Status.IN_PROGRESS else final_record(state)
    conversation.save()
    return conversation


@pytest.fixture
def recruiter(client, django_user_model):
    user = django_user_model.objects.create_user("recruiter", password="pw-for-tests-only")
    client.force_login(user)
    return user


def names(response) -> list[str]:
    return [row.name for row in response.context["rows"]]


# Access


@pytest.mark.parametrize("url_name", ["dashboard_queue", "dashboard_export"])
def test_dashboard_requires_login(client, db, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_detail_and_review_require_login(client, db):
    conversation = make_conversation("Laura Pérez")
    assert client.get(reverse("dashboard_detail", args=[conversation.pk])).status_code == 302
    response = client.post(
        reverse("dashboard_review", args=[conversation.pk]), {"action": "approve"}
    )
    assert response.status_code == 302
    assert not ReviewAction.objects.exists()


def test_login_page_renders(client, db):
    assert client.get(reverse("login")).status_code == 200


# Queue


def test_queue_puts_qualified_and_needs_review_first(client, recruiter):
    make_conversation("Dani", Status.DISQUALIFIED)
    make_conversation("Iker", Status.IN_PROGRESS)
    make_conversation("Laura", Status.QUALIFIED)
    make_conversation("Marta", Status.NEEDS_REVIEW, flag_license=True)

    response = client.get(reverse("dashboard_queue"))
    assert names(response) == ["Laura", "Marta", "Iker", "Dani"]
    tabs = {value: count for value, _, count in response.context["tabs"]}
    assert tabs["qualified"] == 1 and tabs["abandoned"] == 0


def test_queue_ranks_by_preference_score_within_a_status(client, recruiter):
    for name, score in [("Ana", 0.0), ("Bea", 1.5), ("Cris", 0.5)]:
        conversation = make_conversation(name)
        Conversation.objects.filter(pk=conversation.pk).update(preference_score=score)
    high_score_but_disqualified = make_conversation("Dani", Status.DISQUALIFIED)
    Conversation.objects.filter(pk=high_score_but_disqualified.pk).update(preference_score=9.0)

    assert names(client.get(reverse("dashboard_queue"))) == ["Bea", "Cris", "Ana", "Dani"]


def test_flags_are_counted_in_the_row(client, recruiter):
    make_conversation("Marta", Status.NEEDS_REVIEW, flag_license=True)
    row = client.get(reverse("dashboard_queue")).context["rows"][0]
    assert row.flag_count == 2  # the flagged field + the license_unclear review reason
    assert (row.city, row.availability, row.schedule) == ("Barcelona", "Part-time", "Evening")


@pytest.mark.parametrize(
    "params, expected",
    [
        ({"status": "needs_review"}, ["Marta"]),
        ({"country": "MX"}, ["Sofía"]),
        ({"city": "cdmx"}, ["Sofía"]),
        ({"availability": "weekends"}, ["Sofía"]),
        ({"availability": "part_time"}, ["Laura", "Marta"]),
        ({"schedule": "morning"}, ["Sofía"]),
        ({"q": "laura"}, ["Laura"]),
        ({"q": "55 1234"}, ["Sofía"]),  # phone digits, typed with spaces
    ],
)
def test_queue_filters(client, recruiter, params, expected):
    make_conversation("Laura", phone="+34600111222")
    make_conversation("Marta", Status.NEEDS_REVIEW)
    make_conversation(
        "Sofía",
        phone="+525512345678",
        country="MX",
        city="cdmx",
        availability=(Availability.WEEKENDS,),
        schedule=(Schedule.MORNING,),
    )
    assert names(client.get(reverse("dashboard_queue"), params)) == expected


def test_htmx_filter_change_returns_only_the_results(client, recruiter):
    make_conversation("Laura")
    response = client.get(reverse("dashboard_queue"), HTTP_HX_REQUEST="true")
    body = response.content.decode()
    assert "<html" not in body and "Laura" in body
    assert 'id="export" hx-swap-oob="true"' in body


# Detail


def test_detail_shows_fields_flags_transcript_and_record(client, recruiter):
    conversation = make_conversation("Marta", Status.NEEDS_REVIEW, flag_license=True)
    Message.objects.create(conversation=conversation, direction="in", kind="inbound", text="hola")
    Message.objects.create(
        conversation=conversation, direction="out", kind="reply", text="old q", suppressed=True
    )
    Message.objects.create(
        conversation=conversation,
        direction="out",
        kind="reply",
        text="¿ciudad?",
        send_error="ConnectionError: down",
    )

    body = client.get(reverse("dashboard_detail", args=[conversation.pk])).content.decode()

    assert "Marta summary." in body
    assert "license expired" in body and "⚑ flagged" in body
    assert 'href="#m-1"' in body  # provenance link to the source message
    assert "not sent: a newer message was waiting" in body
    assert "send failed: ConnectionError: down" in body
    assert "license_unclear" in body
    assert "&quot;status&quot;: &quot;needs_review&quot;" in body  # final JSON
    assert body.count('type="radio" name="action"') == 4  # the decision buttons post a value


# Review actions


def test_approve_overrides_status_everywhere_and_is_logged(client, recruiter):
    conversation = make_conversation("Marta", Status.NEEDS_REVIEW, flag_license=True)
    response = client.post(
        reverse("dashboard_review", args=[conversation.pk]),
        {"action": "approve", "note": "license renewed, checked by phone"},
    )
    assert response.status_code == 302

    conversation.refresh_from_db()
    assert conversation.status == Status.QUALIFIED
    assert conversation.state["status"] == "qualified"
    assert conversation.final_record["status"] == "qualified"
    review = ReviewAction.objects.get()
    assert (review.action, review.user, review.note) == (
        "approve",
        recruiter,
        "license renewed, checked by phone",
    )
    event = Event.objects.get(type="recruiter_override")
    assert event.data == {
        "from": "needs_review",
        "to": "qualified",
        "by": "recruiter",
        "note": "license renewed, checked by phone",
    }


def test_note_is_logged_without_changing_the_status(client, recruiter):
    conversation = make_conversation("Laura")
    client.post(
        reverse("dashboard_review", args=[conversation.pk]), {"action": "note", "note": "x"}
    )
    conversation.refresh_from_db()
    assert conversation.status == Status.QUALIFIED
    assert ReviewAction.objects.get().action == "note"
    assert not Event.objects.filter(type="recruiter_override").exists()


def test_override_survives_the_candidates_next_message(client, recruiter, engine, channel):
    conversation = make_conversation("Iker", Status.IN_PROGRESS)
    client.post(reverse("dashboard_review", args=[conversation.pk]), {"action": "reject"})

    services.store_inbound(conversation, "¿hola?")
    while services.work_once():
        pass

    conversation.refresh_from_db()
    assert conversation.status == Status.DISQUALIFIED
    assert conversation.next_tick_at is None


def test_review_without_an_action_changes_nothing(client, recruiter):
    conversation = make_conversation("Laura")
    client.post(reverse("dashboard_review", args=[conversation.pk]), {"note": "?"})
    assert not ReviewAction.objects.exists()


# CSV export


def test_export_is_the_filtered_queue_as_csv(client, recruiter):
    make_conversation(
        "Laura", phone="+34600111222", availability=(Availability.PART_TIME, Availability.WEEKENDS)
    )
    make_conversation("Dani", Status.DISQUALIFIED)

    response = client.get(reverse("dashboard_export"), {"status": "qualified"})

    assert response["Content-Type"].startswith("text/csv")
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    assert [r["full_name"] for r in rows] == ["Laura"]
    assert rows[0]["phone"] == "+34600111222"
    assert rows[0]["availability"] == "part_time;weekends"
    assert rows[0]["city"] == "barcelona"
    assert rows[0]["start_date"] == "2026-10-19"

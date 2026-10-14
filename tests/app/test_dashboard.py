import csv
import io

import pytest
from django.urls import reverse

from apps.candidates.models import Candidate, Conversation, ReviewAction
from apps.messaging import services
from apps.messaging.models import Event, Message
from screening.config import load_config
from screening.record import final_record
from screening.schemas import Channel, ConversationState, FieldStatus, FieldValue, Stage, Status
from screening.scoring import preference_score

CONFIG = load_config()


def make_conversation(
    name: str,
    status: Status = Status.QUALIFIED,
    *,
    vacancy: str = "driver",
    phone: str | None = None,
    city: str = "barcelona",
    country: str = "ES",
    availability: tuple[str, ...] = ("part_time",),
    schedule: tuple[str, ...] = ("evening",),
    flag_license: bool = False,
    preferred: dict[str, bool] | None = None,
) -> Conversation:
    """A conversation as the worker would have stored it, for the `driver` or `kitchen_prep` job."""
    conversation = Conversation.objects.create(
        candidate=Candidate.objects.create(name=name, phone=phone),
        channel=Conversation.Channel.WHATSAPP if phone else Conversation.Channel.WEB,
        vacancy_id=vacancy,
    )
    state = ConversationState(
        conversation_id=str(conversation.pk),
        channel=Channel.WEB,
        vacancy_id=vacancy,
        status=status,
        stage=Stage.COLLECTING if status == Status.IN_PROGRESS else Stage.DONE,
        current_field="schedule" if status == Status.IN_PROGRESS else None,
    )

    def accepted(value, source=None):
        return FieldValue(value=value, status=FieldStatus.ACCEPTED, source_message_id=source)

    fields = {
        "full_name": accepted(name, source="1"),
        "location": accepted({"country": country, "city": city}),
        "availability": accepted(list(availability)),
        "schedule": accepted(list(schedule)),
        "start_date": accepted("2026-10-19"),
    }
    if vacancy == "driver":
        fields["has_driver_license"] = (
            FieldValue(status=FieldStatus.FLAGGED, note="license expired")
            if flag_license
            else accepted(True)
        )
        fields["experience"] = accepted([{"platform": "glovo", "years": 1.5}])
    for field_name, value in (preferred or {}).items():
        fields[field_name] = accepted(value)
    state.profile.fields = fields
    if flag_license:
        state.review_reasons = ["license_unclear"]
    state.summary = f"{name} summary."
    state.preference_score = preference_score(CONFIG.vacancy(vacancy), state.profile.fields)
    # Through JSON, exactly as the worker stores it.
    state = ConversationState.model_validate(state.model_dump(mode="json"))
    conversation.state = state.model_dump(mode="json")
    conversation.status = status
    conversation.stage = state.stage
    conversation.country, conversation.city = country, city
    conversation.summary = state.summary
    conversation.preference_score = state.preference_score
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
    """The D25 tie-break: equally qualified kitchen candidates, the license holder first."""
    make_conversation("Ana", vacancy="kitchen_prep", preferred={"has_driver_license": False})
    make_conversation("Bea", vacancy="kitchen_prep", preferred={"has_driver_license": True})
    make_conversation("Cris", vacancy="kitchen_prep", preferred={"food_handler_certificate": True})
    make_conversation(
        "Dani",
        Status.DISQUALIFIED,
        vacancy="kitchen_prep",
        preferred={"has_driver_license": True, "food_handler_certificate": True},
    )
    response = client.get(reverse("dashboard_queue"))
    assert names(response) == ["Bea", "Cris", "Ana", "Dani"]  # 1.5, 1.0, 0, then other status
    scores = [row.conversation.preference_score for row in response.context["rows"]]
    assert scores == [1.5, 1.0, 0.0, 2.5]


def test_flags_are_counted_in_the_row(client, recruiter):
    make_conversation("Marta", Status.NEEDS_REVIEW, flag_license=True)
    row = client.get(reverse("dashboard_queue")).context["rows"][0]
    assert row.flag_count == 2  # the flagged field + the license_unclear review reason
    assert (row.city, row.availability, row.schedule) == ("Barcelona", "Part-time", "Evenings")
    assert row.vacancy == "Delivery driver"


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
        ({"vacancy": "kitchen_prep"}, ["Sofía"]),
        ({"vacancy": "driver"}, ["Laura", "Marta"]),
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
        vacancy="kitchen_prep",
        availability=("weekends",),
        schedule=("morning",),
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
    assert "Driver license" in body and "Glovo 1.5y" in body
    assert 'href="#m-1"' in body  # provenance link to the source message
    assert "not sent: a newer message was waiting" in body
    assert "send failed: ConnectionError: down" in body
    assert "license_unclear" in body
    assert "&quot;status&quot;: &quot;needs_review&quot;" in body  # final JSON
    assert body.count('type="radio" name="action"') == 4  # the decision buttons post a value


def test_detail_shows_preferred_fields_with_weight_and_points(client, recruiter):
    conversation = make_conversation(
        "Ana",
        vacancy="kitchen_prep",
        preferred={"has_driver_license": True, "food_handler_certificate": False},
    )
    response = client.get(reverse("dashboard_detail", args=[conversation.pk]))
    lines = {line.label: line for line in response.context["fields"]}
    assert list(lines)[-2:] == ["Driver license", "Food handler certificate"]  # asked last
    assert (lines["Name"].requirement, lines["Name"].points) == ("required", None)
    license_line, certificate = lines["Driver license"], lines["Food handler certificate"]
    assert (license_line.requirement, license_line.weight, license_line.points) == (
        "preferred",
        1.5,
        1.5,
    )
    assert (certificate.value, certificate.points) == ("No", 0.0)
    body = response.content.decode()
    assert "Kitchen prep assistant" in body and "preference score 1.5" in body
    assert "preferred · weight 1.5" in body


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
    make_conversation("Laura", phone="+34600111222", availability=("part_time", "weekends"))
    make_conversation("Ana", vacancy="kitchen_prep", preferred={"food_handler_certificate": True})
    make_conversation("Dani", Status.DISQUALIFIED)

    response = client.get(reverse("dashboard_export"), {"status": "qualified"})

    assert response["Content-Type"].startswith("text/csv")
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    laura, ana = sorted(rows, key=lambda r: r["full_name"], reverse=True)
    assert [r["full_name"] for r in (laura, ana)] == ["Laura", "Ana"]
    assert (laura["vacancy_id"], laura["phone"]) == ("driver", "+34600111222")
    assert laura["availability"] == "part_time;weekends"
    assert (laura["country"], laura["city"]) == ("ES", "barcelona")
    assert laura["start_date"] == "2026-10-19"
    assert laura["has_driver_license"] == "yes" and laura["experience"] == "glovo:1.5"
    # One column set for every job: a field the job doesn't ask is just empty.
    assert laura["food_handler_certificate"] == "" and ana["experience"] == ""
    assert (ana["food_handler_certificate"], ana["preference_score"]) == ("yes", "1")

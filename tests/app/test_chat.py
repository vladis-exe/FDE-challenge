import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.candidates.models import Conversation
from apps.messaging import services
from apps.messaging.models import Message

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def chat(client, db, engine, channel) -> Conversation:
    response = client.post(
        reverse("chat_start"), {"vacancy": "kitchen_prep", "country": "MX", "language": "en"}
    )
    assert response.status_code == 302
    return Conversation.objects.get()


def test_job_ad_page_renders(client, db):
    response = client.get(reverse("chat_start"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Chatear con Alex" in body
    # Real inputs, not <option>s: the picker must post a value when clicked.
    assert body.count('type="radio" name="country"') == 2
    assert body.count('type="radio" name="language"') == 2
    assert body.count('type="radio" name="vacancy"') == 2  # driver and kitchen_prep
    assert "Ayudante de cocina" in body


def test_job_ad_link_preselects_its_vacancy(client, db):
    body = client.get(reverse("chat_start"), {"vacancy": "kitchen_prep"}).content.decode()
    assert 'value="kitchen_prep" id="id_vacancy_1" required checked' in body


def test_starting_a_chat_creates_a_web_conversation_with_the_opening_message(client, chat):
    assert chat.channel == Conversation.Channel.WEB
    assert (chat.language, chat.country) == ("en", "MX")
    assert chat.vacancy_id == chat.state["vacancy_id"] == "kitchen_prep"
    assert chat.candidate.phone is None

    response = client.get(reverse("chat_thread", args=[chat.pk]))
    assert response.status_code == 200
    assert "Hola, soy Alex (IA)" in response.content.decode()


@pytest.mark.parametrize(
    "data",
    [
        {"vacancy": "driver", "country": "FR", "language": "es"},
        {"vacancy": "astronaut", "country": "ES", "language": "es"},  # unknown: a form error
    ],
)
def test_invalid_picker_shows_the_form_again(client, db, data):
    response = client.post(reverse("chat_start"), data)
    assert response.status_code == 200
    assert not Conversation.objects.exists()


def test_a_chat_is_only_visible_to_the_session_that_started_it(chat):
    stranger = Client()
    assert stranger.get(reverse("chat_thread", args=[chat.pk])).status_code == 404
    assert stranger.post(reverse("chat_send", args=[chat.pk]), {"text": "x"}).status_code == 404
    assert stranger.get(reverse("chat_poll", args=[chat.pk])).status_code == 404


def test_htmx_send_queues_the_message_and_triggers_a_poll(client, chat):
    response = client.post(reverse("chat_send", args=[chat.pk]), {"text": "hi there"}, **HTMX)
    assert response.status_code == 204
    assert json.loads(response.headers["HX-Trigger"]) == {"chat:poll": {}}
    message = chat.messages.get(direction="in")
    assert (message.text, message.processed_at) == ("hi there", None)


def test_plain_send_redirects_back_to_the_chat(client, chat):
    response = client.post(reverse("chat_send", args=[chat.pk]), {"text": "hi"})
    assert response.status_code == 302


def test_empty_send_stores_nothing(client, chat):
    client.post(reverse("chat_send", args=[chat.pk]), {"text": "   "}, **HTMX)
    assert not chat.messages.filter(direction="in").exists()


def test_poll_returns_only_newer_visible_messages_and_the_typing_state(client, chat):
    opening = chat.messages.get()
    client.post(reverse("chat_send", args=[chat.pk]), {"text": "first"}, **HTMX)
    Message.objects.create(
        conversation=chat, direction="out", kind="reply", text="stale reply", suppressed=True
    )

    body = client.get(reverse("chat_poll", args=[chat.pk]), {"after": opening.pk}).content.decode()

    assert "first" in body
    assert "Hola, soy Alex" not in body  # already on the page
    assert "stale reply" not in body  # suppressed replies never reach the candidate
    assert 'id="typing" class="typing" hx-swap-oob="true"' in body  # visible: reply pending
    last = chat.messages.filter(direction="in").get().pk
    assert f"?after={last}" in body


def test_full_round_trip_through_the_worker(client, chat):
    client.post(reverse("chat_send", args=[chat.pk]), {"text": "hello"}, **HTMX)
    while services.work_once():
        pass

    body = client.get(reverse("chat_poll", args=[chat.pk]), {"after": 0}).content.decode()
    assert "hello" in body and "echo: hello" in body
    assert 'id="typing" class="typing" hidden' in body

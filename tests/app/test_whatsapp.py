from types import SimpleNamespace

import pytest
from django.conf import settings
from django.urls import reverse
from twilio.request_validator import RequestValidator

from apps.candidates.models import Candidate, Conversation
from apps.messaging import channels
from apps.messaging.models import Message
from apps.messaging.whatsapp import media_kind, normalize_phone
from screening.schemas import OutboundMessage

TOKEN = "test-auth-token"
BASE = "https://sazon.example"


@pytest.fixture(autouse=True)
def twilio_settings(settings):
    settings.TWILIO_AUTH_TOKEN = TOKEN
    settings.PUBLIC_BASE_URL = BASE
    settings.TWILIO_WHATSAPP_FROM = "+14155238886"


def post_webhook(client, *, signature: str | None = None, **params):
    params = {"MessageSid": "SM1", "From": "whatsapp:+34600111222", "Body": "hola", **params}
    url = reverse("twilio_webhook")
    if signature is None:
        signature = RequestValidator(TOKEN).compute_signature(BASE + url, params)
    return client.post(url, params, HTTP_X_TWILIO_SIGNATURE=signature)


# Signature validation


def test_valid_signature_is_accepted_with_an_empty_twiml_reply(client, db, engine, channel):
    response = post_webhook(client)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/xml"
    assert b"<Response></Response>" in response.content
    assert Message.objects.filter(direction="in", provider_sid="SM1").exists()


@pytest.mark.parametrize("signature", ["", "forged"])
def test_bad_signature_is_rejected_and_nothing_is_stored(client, db, engine, signature):
    assert post_webhook(client, signature=signature).status_code == 403
    assert not Message.objects.exists()
    assert not Candidate.objects.exists()


def test_tampered_body_fails_the_signature(client, db, engine):
    url = reverse("twilio_webhook")
    params = {"MessageSid": "SM1", "From": "whatsapp:+34600111222", "Body": "hola"}
    signature = RequestValidator(TOKEN).compute_signature(BASE + url, params)
    response = client.post(url, {**params, "Body": "tampered"}, HTTP_X_TWILIO_SIGNATURE=signature)
    assert response.status_code == 403


# Idempotency


def test_redelivered_message_sid_is_stored_once(client, db, engine, channel):
    post_webhook(client)
    post_webhook(client)
    assert Message.objects.filter(direction="in").count() == 1
    assert Conversation.objects.count() == 1


# Routing


def test_first_message_from_a_new_phone_opens_a_conversation_then_queues(
    client, db, engine, channel
):
    post_webhook(client, Body="vi el anuncio")

    conversation = Conversation.objects.get()
    assert conversation.channel == Conversation.Channel.WHATSAPP
    assert conversation.candidate.phone == "+34600111222"
    assert conversation.vacancy_id == settings.WHATSAPP_VACANCY == "driver"
    assert [s.text for s in channel.sent] == ["Hola, soy Alex (IA)"]  # opening went out
    inbound = conversation.messages.get(direction="in")
    assert (inbound.text, inbound.processed_at) == ("vi el anuncio", None)


def test_known_phone_resumes_its_latest_conversation_even_after_an_outcome(
    client, db, engine, channel
):
    post_webhook(client, MessageSid="SM1")
    Conversation.objects.update(status=Conversation.Status.QUALIFIED)
    post_webhook(client, MessageSid="SM2", Body="¿cuándo me llaman?")

    conversation = Conversation.objects.get()
    assert conversation.messages.filter(direction="in").count() == 2


def test_mexican_plus_521_reaches_the_candidate_who_applied_with_plus_52(
    client, db, engine, channel
):
    candidate = Candidate.objects.create(phone="+525512345678")
    post_webhook(client, From="whatsapp:+5215512345678")
    assert Conversation.objects.get().candidate == candidate


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("whatsapp:+34600111222", "+34600111222"),
        ("whatsapp:+5215512345678", "+525512345678"),
        ("+525512345678", "+525512345678"),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


# Media


@pytest.mark.parametrize(
    "num, content_type, expected",
    [
        ("0", "", "none"),
        ("1", "audio/ogg", "audio"),
        ("1", "image/webp", "sticker"),
        ("1", "image/jpeg", "image"),
        ("1", "video/mp4", "other"),
    ],
)
def test_media_kind(num, content_type, expected):
    assert media_kind(num, content_type) == expected


def test_voice_note_is_stored_as_audio(client, db, engine, channel):
    post_webhook(client, Body="", NumMedia="1", MediaContentType0="audio/ogg")
    assert Message.objects.get(direction="in").media == "audio"


# Sending


def test_whatsapp_channel_sends_through_twilio(db, monkeypatch):
    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(sid="SMout1")

    monkeypatch.setattr(channels, "twilio_client", lambda: SimpleNamespace(messages=FakeMessages()))
    conversation = Conversation.objects.create(
        candidate=Candidate.objects.create(phone="+34600111222"),
        channel=Conversation.Channel.WHATSAPP,
    )

    sid = channels.WhatsAppChannel().send(conversation, OutboundMessage(text="hola", kind="reply"))

    assert sid == "SMout1"
    assert calls == [
        {"from_": "whatsapp:+14155238886", "to": "whatsapp:+34600111222", "body": "hola"}
    ]


# /apply/


def test_apply_starts_an_agent_initiated_whatsapp_conversation(client, db, engine, channel):
    response = client.post(
        reverse("apply"),
        {
            "vacancy": "kitchen_prep",
            "name": "Laura Pérez",
            "country": "ES",
            "phone": "612 345 678",
            "language": "es",
        },
    )
    assert response.status_code == 200
    assert "Revisa tu WhatsApp" in response.content.decode()
    conversation = Conversation.objects.get()
    assert conversation.channel == Conversation.Channel.WHATSAPP
    assert conversation.candidate.phone == "+34612345678"
    assert conversation.candidate.name == "Laura Pérez"
    assert conversation.country == "ES"
    assert conversation.vacancy_id == "kitchen_prep"
    assert [s.text for s in channel.sent] == ["Hola, soy Alex (IA)"]


def test_applying_twice_resumes_instead_of_starting_over(client, db, engine, channel):
    data = {
        "vacancy": "driver",
        "name": "Laura Pérez",
        "country": "MX",
        "phone": "55 1234 5678",
        "language": "es",
    }
    client.post(reverse("apply"), data)
    response = client.post(reverse("apply"), data)
    assert "Ya tenemos tu solicitud" in response.content.decode()
    assert Conversation.objects.count() == 1
    assert len(channel.sent) == 1


def test_applying_to_another_job_starts_a_second_screening(client, db, engine, channel):
    data = {"name": "Laura Pérez", "country": "ES", "phone": "612 345 678", "language": "es"}
    client.post(reverse("apply"), {**data, "vacancy": "driver"})
    client.post(reverse("apply"), {**data, "vacancy": "kitchen_prep"})
    vacancies = Conversation.objects.order_by("started_at").values_list("vacancy_id", flat=True)
    assert list(vacancies) == ["driver", "kitchen_prep"]
    assert len(channel.sent) == 2


def test_apply_rejects_an_invalid_phone(client, db, engine):
    response = client.post(
        reverse("apply"), {"name": "Laura", "country": "ES", "phone": "123", "language": "es"}
    )
    assert "Número no válido" in response.content.decode()
    assert not Conversation.objects.exists()

import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.candidates.models import Candidate, Conversation
from apps.messaging.models import Message


@pytest.fixture
def conversation(db) -> Conversation:
    candidate = Candidate.objects.create(phone="+34600111222", name="Laura Pérez")
    return Conversation.objects.create(candidate=candidate, channel=Conversation.Channel.WHATSAPP)


def test_phone_is_unique(conversation):
    with pytest.raises(IntegrityError):
        Candidate.objects.create(phone="+34600111222")


def test_web_candidates_can_share_a_null_phone(db):
    Candidate.objects.create()
    Candidate.objects.create()
    assert Candidate.objects.filter(phone__isnull=True).count() == 2


def test_provider_sid_is_unique(conversation):
    Message.objects.create(
        conversation=conversation, direction="in", kind="inbound", provider_sid="SM1"
    )
    with pytest.raises(IntegrityError):
        Message.objects.create(
            conversation=conversation, direction="in", kind="inbound", provider_sid="SM1"
        )


def test_masked_phone_hides_the_middle(conversation):
    assert conversation.candidate.masked_phone == "+346…222"


def test_new_conversation_defaults_to_in_progress(conversation):
    assert conversation.status == Conversation.Status.IN_PROGRESS
    assert conversation.state == {}


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:candidates_conversation_changelist",
        "admin:candidates_candidate_changelist",
        "admin:messaging_message_changelist",
        "admin:messaging_event_changelist",
    ],
)
def test_admin_changelists_render(admin_client, conversation, url_name):
    assert admin_client.get(reverse(url_name)).status_code == 200


def test_admin_conversation_detail_renders(admin_client, conversation):
    url = reverse("admin:candidates_conversation_change", args=[conversation.pk])
    assert admin_client.get(url).status_code == 200

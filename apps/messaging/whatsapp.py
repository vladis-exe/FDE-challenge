"""WhatsApp entry points (CONTRACTS §5): the Twilio webhook and the `/apply/` form.

The webhook only validates, stores and returns; the worker does the rest. In production the
`/apply/` opening message (business-initiated, outside the 24 h window) needs an approved
template; the Twilio sandbox lets us send it as free text to numbers that joined the sandbox.
"""

import logging

import phonenumbers
from django import forms
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from twilio.request_validator import RequestValidator

from apps.candidates.models import Candidate, Conversation
from apps.messaging import services
from apps.messaging.models import Message

log = logging.getLogger(__name__)

# Twilio's "do nothing" reply: we answer later, from the worker.
EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def normalize_phone(raw: str) -> str:
    """E.164 for a WhatsApp address or an international number ("whatsapp:+34…" → "+34…").

    Mexican mobiles often arrive from WhatsApp as +52 1 …, the pre-2019 mobile prefix. Dropping
    the 1 makes them match the +52 … number the candidate typed on the apply form.
    """
    phone = raw.removeprefix("whatsapp:").strip()
    if phone.startswith("+521") and len(phone) == 14:
        phone = "+52" + phone[4:]
    return phone


def media_kind(num_media: str, content_type: str) -> str:
    if not num_media or num_media == "0":
        return Message.Media.NONE
    if content_type.startswith("audio/"):
        return Message.Media.AUDIO
    if content_type == "image/webp":  # WhatsApp stickers
        return Message.Media.STICKER
    if content_type.startswith("image/"):
        return Message.Media.IMAGE
    return Message.Media.OTHER


@csrf_exempt
@require_POST
def twilio_webhook(request: HttpRequest) -> HttpResponse:
    # Twilio signs the public URL it called; behind a proxy request.build_absolute_uri() can differ.
    url = settings.PUBLIC_BASE_URL + request.get_full_path()
    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    if not validator.validate(url, request.POST.dict(), signature):
        log.warning("rejected Twilio webhook with an invalid signature")
        return HttpResponseForbidden()

    sid = request.POST.get("MessageSid", "")
    if not sid or Message.objects.filter(provider_sid=sid).exists():
        return _empty_twiml()  # a retried delivery, or not a message at all

    phone = normalize_phone(request.POST.get("From", ""))
    with transaction.atomic():
        candidate, _ = Candidate.objects.get_or_create(phone=phone)
        conversation = (
            candidate.conversations.filter(channel=Conversation.Channel.WHATSAPP)
            .order_by("-started_at")
            .first()
        )
    if conversation is None:
        # The candidate wrote first (e.g. from a job ad): open with the AI disclosure and
        # consent question, then their message is processed like any other.
        conversation = services.start_conversation(candidate, Conversation.Channel.WHATSAPP)

    services.store_inbound(
        conversation,
        request.POST.get("Body", ""),
        media=media_kind(
            request.POST.get("NumMedia", "0"), request.POST.get("MediaContentType0", "")
        ),
        provider_sid=sid,
    )
    return _empty_twiml()


class ApplyForm(forms.Form):
    name = forms.CharField(max_length=200, label="Nombre y apellidos")
    country = forms.ChoiceField(choices=[("ES", "España"), ("MX", "México")], label="País")
    phone = forms.CharField(max_length=32, label="Móvil (WhatsApp)")
    language = forms.ChoiceField(choices=[("es", "Español"), ("en", "English")], label="Idioma")

    def clean(self):
        data = super().clean()
        if "phone" in data and "country" in data:
            try:
                number = phonenumbers.parse(data["phone"], data["country"])
            except phonenumbers.NumberParseException:
                number = None
            if number is None or not phonenumbers.is_valid_number(number):
                self.add_error("phone", "Número no válido.")
            else:
                data["phone"] = phonenumbers.format_number(
                    number, phonenumbers.PhoneNumberFormat.E164
                )
        return data


def apply(request: HttpRequest) -> HttpResponse:
    """An application form; the agent then messages the candidate first on WhatsApp."""
    form = ApplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        candidate, _ = Candidate.objects.get_or_create(
            phone=data["phone"], defaults={"name": data["name"]}
        )
        resumed = candidate.conversations.filter(channel=Conversation.Channel.WHATSAPP).exists()
        if not resumed:
            services.start_conversation(
                candidate,
                Conversation.Channel.WHATSAPP,
                language=data["language"],
                country=data["country"],
            )
        return render(request, "apply/sent.html", {"resumed": resumed})
    return render(request, "apply/form.html", {"form": form})


def _empty_twiml() -> HttpResponse:
    return HttpResponse(EMPTY_TWIML, content_type="text/xml")

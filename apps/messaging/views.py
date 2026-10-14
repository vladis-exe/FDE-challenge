"""Web chat (CONTRACTS §5 `/chat/`): a simulated job-ad link and a phone-style chat page.

The page polls for new messages; the worker produces the replies, exactly as for WhatsApp.
"""

from uuid import UUID
from zoneinfo import ZoneInfo

from django import forms
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django_htmx.http import trigger_client_event

from apps.candidates.models import Candidate, Conversation
from apps.messaging import services
from apps.messaging.models import Message

# Conversations this browser started; a chat is only visible to the session that opened it.
SESSION_KEY = "chat_conversations"

UI_TEXT = {
    "es": {
        "subtitle": "Grupo Sazón · asistente virtual (IA)",
        "placeholder": "Escribe un mensaje",
        "send": "Enviar",
        "typing": "Alex está escribiendo…",
    },
    "en": {
        "subtitle": "Grupo Sazón · virtual assistant (AI)",
        "placeholder": "Type a message",
        "send": "Send",
        "typing": "Alex is typing…",
    },
}


class StartChatForm(forms.Form):
    vacancy = forms.ChoiceField(widget=forms.RadioSelect)
    country = forms.ChoiceField(
        choices=[("ES", "España"), ("MX", "México")], widget=forms.RadioSelect
    )
    language = forms.ChoiceField(
        choices=[("es", "Español"), ("en", "English")], widget=forms.RadioSelect, initial="es"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vacancy"].choices = services.vacancy_choices()


class SendForm(forms.Form):
    text = forms.CharField(max_length=2000)


def chat_start(request: HttpRequest) -> HttpResponse:
    # One link per job ad in production (`/chat/?vacancy=driver`); the picker is a demo convenience.
    form = StartChatForm(request.POST or None, initial={"vacancy": request.GET.get("vacancy")})
    if request.method == "POST" and form.is_valid():
        conversation = services.start_conversation(
            Candidate.objects.create(),
            Conversation.Channel.WEB,
            vacancy_id=form.cleaned_data["vacancy"],
            language=form.cleaned_data["language"],
            country=form.cleaned_data["country"],
        )
        request.session[SESSION_KEY] = [*request.session.get(SESSION_KEY, []), str(conversation.pk)]
        return redirect("chat_thread", conversation_id=conversation.pk)
    return render(request, "chat/start.html", {"form": form})


@require_GET
def chat_thread(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = _own_conversation(request, conversation_id)
    messages = list(_visible_messages(conversation))
    return render(
        request,
        "chat/thread.html",
        {
            "conversation": conversation,
            "messages": messages,
            "last_id": messages[-1].pk if messages else 0,
            "typing": _agent_is_typing(conversation),
            "ui": UI_TEXT.get(conversation.language, UI_TEXT["es"]),
        },
    )


@require_POST
def chat_send(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = _own_conversation(request, conversation_id)
    form = SendForm(request.POST)
    if form.is_valid():
        services.store_inbound(conversation, form.cleaned_data["text"])
    if not request.htmx:
        return redirect("chat_thread", conversation_id=conversation.pk)
    # The poller shows the new bubble; ask it to run now instead of at its next tick.
    return trigger_client_event(HttpResponse(status=204), "chat:poll")


@require_GET
def chat_poll(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = _own_conversation(request, conversation_id)
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    messages = list(_visible_messages(conversation).filter(pk__gt=after))
    return render(
        request,
        "chat/_poll.html",
        {
            "conversation": conversation,
            "messages": messages,
            "last_id": messages[-1].pk if messages else after,
            "typing": _agent_is_typing(conversation),
            "ui": UI_TEXT.get(conversation.language, UI_TEXT["es"]),
        },
    )


def _own_conversation(request: HttpRequest, conversation_id: UUID) -> Conversation:
    if str(conversation_id) not in request.session.get(SESSION_KEY, []):
        raise Http404
    conversation = get_object_or_404(
        Conversation, pk=conversation_id, channel=Conversation.Channel.WEB
    )
    # Bubble times in the candidate's local time.
    country = conversation.country or "ES"
    timezone.activate(ZoneInfo(services.engine_context().config.timezone_for(country)))
    return conversation


def _visible_messages(conversation: Conversation) -> QuerySet[Message]:
    """Everything the candidate sent, plus the replies that were actually sent to them."""
    return conversation.messages.filter(Q(direction=Message.Direction.IN) | Q(suppressed=False))


def _agent_is_typing(conversation: Conversation) -> bool:
    return conversation.messages.filter(
        direction=Message.Direction.IN, processed_at__isnull=True
    ).exists()

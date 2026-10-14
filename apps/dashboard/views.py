"""Recruiter dashboard: the queue, a candidate's detail page, review actions and CSV export."""

import csv
import json
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.candidates.models import Conversation, ReviewAction
from apps.dashboard import presenters, services
from screening.schemas import Availability, ConversationState, Schedule

PAGE_SIZE = 50
ANY = [("", "Any")]


class QueueFilters(forms.Form):
    q = forms.CharField(required=False)
    status = forms.ChoiceField(required=False, choices=ANY + Conversation.Status.choices)
    country = forms.ChoiceField(required=False, choices=ANY + [("ES", "Spain"), ("MX", "Mexico")])
    city = forms.ChoiceField(required=False)
    availability = forms.ChoiceField(
        required=False, choices=ANY + [(a.value, presenters.OPTION_LABELS[a]) for a in Availability]
    )
    schedule = forms.ChoiceField(
        required=False, choices=ANY + [(s.value, presenters.OPTION_LABELS[s]) for s in Schedule]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].choices = ANY + presenters.city_choices()


class ReviewForm(forms.Form):
    action = forms.ChoiceField(choices=ReviewAction.Action.choices, widget=forms.RadioSelect)
    note = forms.CharField(
        required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 2})
    )


def _filtered(request: HttpRequest) -> tuple[QueueFilters, QuerySet[Conversation]]:
    form = QueueFilters(request.GET)
    criteria = form.cleaned_data if form.is_valid() else {}
    return form, services.queue(**criteria)


@login_required
@require_GET
def queue(request: HttpRequest) -> HttpResponse:
    form, conversations = _filtered(request)
    page = Paginator(conversations, PAGE_SIZE).get_page(request.GET.get("page"))
    counts = dict(Conversation.objects.values_list("status").annotate(n=Count("id")).order_by())
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "form": form,
        "page": page,
        "rows": [presenters.row(c) for c in page.object_list],
        "tabs": [
            (status.value, status.label, counts.get(status, 0))
            for status in services.STATUS_PRIORITY
        ],
        "params": params.urlencode(),
    }
    # Filter changes swap only the results; the full page is for the first load and reloads.
    template = "dashboard/_results.html" if request.htmx else "dashboard/queue.html"
    return render(request, template, context)


@login_required
@require_GET
def detail(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = get_object_or_404(
        Conversation.objects.select_related("candidate"), pk=conversation_id
    )
    state = ConversationState.model_validate(conversation.state)
    record = presenters.record_for(conversation)
    return render(
        request,
        "dashboard/detail.html",
        {
            "conversation": conversation,
            "state": state,
            "record": record,
            "record_json": json.dumps(record, indent=2, ensure_ascii=False),
            "fields": presenters.field_lines(state),
            "transcript": conversation.messages.order_by("id"),
            "events": conversation.events.order_by("created_at", "id"),
            "reviews": conversation.review_actions.select_related("user"),
            "review_form": ReviewForm(),
        },
    )


@login_required
@require_POST
def review(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    form = ReviewForm(request.POST)
    if form.is_valid():
        services.record_review(
            conversation, request.user, form.cleaned_data["action"], form.cleaned_data["note"]
        )
        messages.success(request, "Saved.")
    else:
        messages.error(request, "Pick an action.")
    return redirect("dashboard_detail", conversation_id=conversation.pk)


CSV_COLUMNS = [
    "conversation_id", "status", "channel", "phone", "full_name", "has_driver_license",
    "country", "city", "availability", "preferred_schedule", "delivery_experience",
    "start_date", "flags", "disqualify_reason", "review_reasons", "language", "started_at",
    "completed_at", "summary",
]  # fmt: skip


@login_required
@require_GET
def export_csv(request: HttpRequest) -> HttpResponse:
    """The current filtered queue as CSV, one row per conversation, from the final record."""
    _, conversations = _filtered(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="candidates.csv"'
    response.write("﻿")  # BOM, so Excel opens the accents correctly
    writer = csv.DictWriter(response, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for conversation in conversations.iterator():
        record = presenters.record_for(conversation)
        writer.writerow(
            {
                **{key: record.get(key) for key in CSV_COLUMNS if key in record},
                "channel": conversation.channel,
                "phone": conversation.candidate.phone or "",
                "availability": ";".join(record["availability"] or []),
                "preferred_schedule": ";".join(record["preferred_schedule"] or []),
                "delivery_experience": ";".join(
                    f"{item['platform']}:{item['years']:g}"
                    for item in record["delivery_experience"] or []
                ),
                "flags": ";".join(f"{f['field']}: {f['note']}" for f in record["flags"]),
                "review_reasons": ";".join(record["review_reasons"]),
                "started_at": conversation.started_at.isoformat(),
                "completed_at": conversation.completed_at.isoformat()
                if conversation.completed_at
                else "",
            }
        )
    return response

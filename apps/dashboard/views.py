"""Recruiter dashboard: the queue, a candidate's detail page, review actions and CSV export."""

import csv
import json
from datetime import timedelta
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.candidates.models import Conversation, ReviewAction
from apps.dashboard import analytics, presenters, services
from screening.schemas import ConversationState

PAGE_SIZE = 50
ANY = [("", "Any")]


class QueueFilters(forms.Form):
    q = forms.CharField(required=False)
    vacancy = forms.ChoiceField(required=False)
    status = forms.ChoiceField(required=False, choices=ANY + Conversation.Status.choices)
    country = forms.ChoiceField(required=False, choices=ANY + [("ES", "Spain"), ("MX", "Mexico")])
    city = forms.ChoiceField(required=False)
    availability = forms.ChoiceField(required=False)
    schedule = forms.ChoiceField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vacancy"].choices = ANY + [
            (vacancy_id, presenters.vacancy_title(vacancy_id))
            for vacancy_id in presenters.vacancies()
        ]
        self.fields["city"].choices = ANY + presenters.city_choices()
        for name in ("availability", "schedule"):
            self.fields[name].choices = ANY + presenters.option_choices(name)


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
    vacancy = presenters.vacancies().get(conversation.vacancy_id)
    if vacancy is None:
        raise Http404(f"unknown vacancy {conversation.vacancy_id!r}")
    record = presenters.record_for(conversation)
    return render(
        request,
        "dashboard/detail.html",
        {
            "conversation": conversation,
            "state": state,
            "record": record,
            "record_json": json.dumps(record, indent=2, ensure_ascii=False),
            "vacancy": vacancy,
            "name": record["fields"].get("full_name") or conversation.candidate.name,
            "fields": presenters.field_lines(state, vacancy),
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


CSV_HEAD = ["conversation_id", "vacancy_id", "status", "channel", "phone", "language"]
CSV_TAIL = [
    "preference_score", "flags", "disqualify_reason", "review_reasons", "started_at",
    "completed_at", "summary",
]  # fmt: skip


def csv_field_columns() -> list[str]:
    """Every field name any vacancy asks, in config order; a city field becomes two columns."""
    columns: list[str] = []
    for vacancy in presenters.vacancies().values():
        for spec in vacancy.asked:
            names = ["country", "city"] if spec.type == "city" else [spec.name]
            columns += [name for name in names if name not in columns]
    return columns


def csv_value(value) -> str:
    """Machine-readable values for spreadsheets: option keys, ISO dates, platform:years."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ";".join(
            f"{item['platform']}:{item['years']:g}" if isinstance(item, dict) else str(item)
            for item in value
        )
    return "" if value is None else str(value)


@login_required
@require_GET
def export_csv(request: HttpRequest) -> HttpResponse:
    """The current filtered queue as CSV, one row per conversation, from the final record.

    One column per field across all vacancies, so a mixed export still lines up; a field
    the conversation's vacancy doesn't ask is simply empty.
    """
    _, conversations = _filtered(request)
    field_columns = csv_field_columns()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="candidates.csv"'
    response.write("\ufeff")  # BOM, so Excel opens the accents correctly
    writer = csv.DictWriter(response, fieldnames=CSV_HEAD + field_columns + CSV_TAIL)
    writer.writeheader()
    for conversation in conversations.iterator():
        record = presenters.record_for(conversation)
        fields = dict(record["fields"])
        vacancy = presenters.vacancies().get(conversation.vacancy_id)
        for spec in vacancy.fields if vacancy else []:
            if spec.type == "city" and spec.name in fields:
                fields.update(fields.pop(spec.name))  # {"country": ..., "city": ...}
        writer.writerow(
            {
                "conversation_id": record["conversation_id"],
                "vacancy_id": conversation.vacancy_id,
                "status": record["status"],
                "channel": conversation.channel,
                "phone": conversation.candidate.phone or "",
                "language": record["language"],
                **{name: csv_value(fields.get(name)) for name in field_columns},
                "preference_score": f"{record['preference_score']:g}",
                "flags": ";".join(f"{f['field']}: {f['note']}" for f in record["flags"]),
                "disqualify_reason": record["disqualify_reason"] or "",
                "review_reasons": ";".join(record["review_reasons"]),
                "started_at": conversation.started_at.isoformat(),
                "completed_at": conversation.completed_at.isoformat()
                if conversation.completed_at
                else "",
                "summary": record["summary"] or "",
            }
        )
    return response


PERIODS = {"7": "Last 7 days", "30": "Last 30 days", "all": "All time"}


@login_required
@require_GET
def analytics_view(request: HttpRequest) -> HttpResponse:
    period = request.GET.get("period", "30")
    if period not in PERIODS:
        period = "30"
    since = None if period == "all" else timezone.now() - timedelta(days=int(period))
    jobs = {
        vacancy_id: presenters.vacancy_title(vacancy_id) for vacancy_id in presenters.vacancies()
    }
    job = request.GET.get("job", "")
    if job not in jobs:
        job = ""
    return render(
        request,
        "dashboard/analytics.html",
        {
            "report": analytics.build(since, vacancy_id=job),
            "period": period,
            "periods": PERIODS,
            "job": job,
            "jobs": jobs,
        },
    )

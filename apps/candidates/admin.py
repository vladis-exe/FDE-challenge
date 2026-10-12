from django.contrib import admin

from apps.messaging.models import Event, Message

from .models import Candidate, Conversation, ReviewAction


class ConversationInline(admin.TabularInline):
    model = Conversation
    fields = ["channel", "status", "stage", "city", "started_at"]
    readonly_fields = fields
    extra = 0
    show_change_link = True


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "created_at"]
    search_fields = ["name", "phone"]
    inlines = [ConversationInline]


class MessageInline(admin.TabularInline):
    model = Message
    fields = [
        "created_at",
        "direction",
        "kind",
        "text",
        "media",
        "processed_at",
        "suppressed",
        "send_error",
    ]
    readonly_fields = fields
    extra = 0
    can_delete = False


class EventInline(admin.TabularInline):
    model = Event
    fields = ["created_at", "type", "data"]
    readonly_fields = fields
    extra = 0
    can_delete = False


class ReviewActionInline(admin.TabularInline):
    model = ReviewAction
    fields = ["created_at", "user", "action", "note"]
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "candidate",
        "channel",
        "status",
        "stage",
        "country",
        "city",
        "started_at",
        "next_tick_at",
    ]
    list_filter = ["status", "channel", "country", "stage"]
    search_fields = ["candidate__name", "candidate__phone", "city"]
    list_select_related = ["candidate"]
    readonly_fields = ["id", "started_at"]
    inlines = [MessageInline, EventInline, ReviewActionInline]


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = ["conversation", "user", "action", "created_at"]
    list_filter = ["action"]

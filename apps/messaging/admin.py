from django.contrib import admin

from .models import Event, Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "conversation",
        "direction",
        "kind",
        "text",
        "processed_at",
        "suppressed",
        "send_error",
    ]
    list_filter = ["direction", "kind", "suppressed", "media"]
    search_fields = ["text", "provider_sid"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["conversation", "type", "created_at"]
    list_filter = ["type"]

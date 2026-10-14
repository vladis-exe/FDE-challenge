from django.urls import path

from apps.messaging import views, whatsapp

urlpatterns = [
    path("chat/", views.chat_start, name="chat_start"),
    path("chat/<uuid:conversation_id>/", views.chat_thread, name="chat_thread"),
    path("chat/<uuid:conversation_id>/send/", views.chat_send, name="chat_send"),
    path("chat/<uuid:conversation_id>/poll/", views.chat_poll, name="chat_poll"),
    path("apply/", whatsapp.apply, name="apply"),
    path("webhooks/twilio/whatsapp/", whatsapp.twilio_webhook, name="twilio_webhook"),
]

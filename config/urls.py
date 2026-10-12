from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="chat_start")),
    path("admin/", admin.site.urls),
    path("", include("apps.messaging.urls")),
]

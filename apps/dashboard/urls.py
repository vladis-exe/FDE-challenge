from django.urls import path

from apps.dashboard import views

urlpatterns = [
    path("", views.queue, name="dashboard_queue"),
    path("export.csv", views.export_csv, name="dashboard_export"),
    path("c/<uuid:conversation_id>/", views.detail, name="dashboard_detail"),
    path("c/<uuid:conversation_id>/review/", views.review, name="dashboard_review"),
]

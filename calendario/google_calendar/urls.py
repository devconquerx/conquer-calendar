from django.urls import path

from .views_webhook import GoogleWebhookView

urlpatterns = [
    path('google-calendar/', GoogleWebhookView.as_view(), name='gcal_webhook'),
]

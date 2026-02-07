from django.urls import path
from .views import (
    CreateCheckoutSessionView,
    stripe_webhook
)

urlpatterns = [
    path('create-checkout/', CreateCheckoutSessionView.as_view()),
    path('webhook/', stripe_webhook),
]
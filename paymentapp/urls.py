from django.urls import path
from .views import (
    CreateCheckoutSessionView,
    stripe_webhook,
    payment_success_view,  # NEW
    payment_cancel_view,    # NEW
    # RetailerMonthlySalesView,
    RetailerMonthlySalesChartView,
    MyOrdersView
)

urlpatterns = [
    path('create-checkout/', CreateCheckoutSessionView.as_view()),
    path('webhook/', stripe_webhook),
    path('success/', payment_success_view, name='payment-success'),  # NEW
    path('cancel/', payment_cancel_view, name='payment-cancel'),      # NEW

    # path('sales/monthly/', RetailerMonthlySalesView.as_view(), name='retailer-monthly-sales'),
    path("retailer/sales/chart/", RetailerMonthlySalesChartView.as_view()),

    path('my-orders/', MyOrdersView.as_view(), name='my-orders'),
]
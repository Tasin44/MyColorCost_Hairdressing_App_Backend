from django.urls import path
from .views import (
    ReferralDashboardView,
    WithdrawalRequestView,
    SubscriptionStatusView,
    revenuecat_webhook,
    MyReferralCodeView  # ✅ Add this
)

urlpatterns = [
    # Referral system
    path('referral/dashboard/', ReferralDashboardView.as_view(), name='referral-dashboard'),
    path('referral/withdraw/', WithdrawalRequestView.as_view(), name='withdrawal-request'),
    
    # Subscription
    path('subscription/status/', SubscriptionStatusView.as_view(), name='subscription-status'),
    
    # RevenueCat webhook
    path('webhook/revenuecat/', revenuecat_webhook, name='revenuecat-webhook'),

    path('referral/my-code/', MyReferralCodeView.as_view(), name='my-referral-code'),  # ✅ Add this

]
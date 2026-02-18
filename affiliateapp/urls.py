from django.urls import path
from .views import (
    ReferralDashboardView,
    WithdrawalRequestView,
    SubscriptionStatusView,
    revenuecat_webhook,
    MyReferralCodeView  ,# ✅ Add this
    ReferralLandingPageView,  # ✅ Add this
    ReferralLandingAPIView ,   # ✅ Add this
    CreateSubscriptionView  # ✅ Add this import
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

    #====================================================================

    path('subscription/create/', CreateSubscriptionView.as_view(), name='subscription-create'),
    
    # Subscription
    path('subscription/status/', SubscriptionStatusView.as_view(), name='subscription-status'),
    
    # RevenueCat webhook
    path('webhook/revenuecat/', revenuecat_webhook, name='revenuecat-webhook'),

    # ✅ Public referral landing page (HTML)
    path('referral/join/', ReferralLandingPageView.as_view(), name='referral-landing'),
    
    # ✅ Public API endpoint (JSON)
    path('referral/info/', ReferralLandingAPIView.as_view(), name='referral-info-api'),
]
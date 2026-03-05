from django.urls import path
from .views import TermsAndConditionsView, PrivacyPolicyView,RetailerTermsView,RetailerPrivacyPolicyView

urlpatterns = [
    path('terms/', TermsAndConditionsView.as_view(), name='terms-and-conditions'),
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy-policy'),
    path(
        "retailer/terms/",
        RetailerTermsView.as_view(),
        name="retailer-terms"
    ),

    path(
        "retailer/privacy-policy/",
        RetailerPrivacyPolicyView.as_view(),
        name="retailer-privacy-policy"
    ),


]
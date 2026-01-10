# urls.py
from django.urls import path
from .views import (
    SignupView, VerifyOTPView, ResendOTPView, LoginView,
    ForgotPasswordView, ResetPasswordView, ProfileUpdateView,
    DeleteUserView, MeView, AccountTypeSetupView,
    SubUserListCreateView, SubUserDetailView
)

urlpatterns = [
    # Auth / Signup / Login
    path('signup/', SignupView.as_view(), name='signup'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', LoginView.as_view(), name='login'),

    # Password reset
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),

    # User profile
    path('profile/update/', ProfileUpdateView.as_view(), name='profile-update'),
    path('profile/delete/', DeleteUserView.as_view(), name='delete-user'),
    path('me/', MeView.as_view(), name='me'),

    # Account type setup
    path('account-type/setup/', AccountTypeSetupView.as_view(), name='account-type-setup'),

    # Sub-user management
    path('sub-users/', SubUserListCreateView.as_view(), name='sub-user-list-create'),
    path('sub-users/<uuid:sub_user_id>/', SubUserDetailView.as_view(), name='sub-user-detail'),
]







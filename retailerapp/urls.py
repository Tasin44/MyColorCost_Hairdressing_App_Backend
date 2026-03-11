from django.urls import path
from .views import (
    RetailerProfileSetupView, RetailerDashboardView,
    RetailerProductListView, RetailerProductCreateView,
    RetailerProductDetailView, MissingProductRequestView,
    DeliveryAddressListCreateView,RetailerStripeCompleteView,RetailerStripeOnboardView,
    RetailerStripeStatusView, retailer_dashboard_view,RetailerOrderListView,RetailerOrderDetailView,RetailerPaymentListView,
    RetailerProfilePublicSetupView,
    # RetailerProfileUpdateView,      # ✅ # ✅ ADDed 28th feb
    RetailerListView,               # ✅ # ✅ ADDed 28th feb
    RetailerPublicDetailView,       # ✅ # ✅ ADDed 28th feb
    RetailerMyProfileView,   # ✅ ADD THIS
    RetailerBulkDiscountView,
    RetailerSingleProductDiscountView
)

app_name = 'retailerapp'

urlpatterns = [
    # ✅ Retailer Profile Setup
    path('profile/setup/', RetailerProfileSetupView.as_view(), name='profile-setup'),
    
    # ✅ Retailer Dashboard
    path('dashboard/', RetailerDashboardView.as_view(), name='dashboard'),
    
    # ✅ Product Management
    path('products/', RetailerProductListView.as_view(), name='product-list'),
    path('products/create/', RetailerProductCreateView.as_view(), name='product-create'),
    path('products/<int:product_id>/', RetailerProductDetailView.as_view(), name='product-detail'),
    
    # ✅ Missing Product Requests
    path('missing-products/', MissingProductRequestView.as_view(), name='missing-product-request'),
    
    # ✅ Delivery Addresses (Customer Side)
    path('delivery-addresses/', DeliveryAddressListCreateView.as_view(), name='delivery-addresses'),

     # ✅ Stripe Connect Onboarding (NEW)
    path('stripe/onboard/', RetailerStripeOnboardView.as_view(), name='stripe-onboard'),
    path('stripe/complete/', RetailerStripeCompleteView.as_view(), name='stripe-complete'),

    path('stripe/status/', RetailerStripeStatusView.as_view(), name='stripe-status'),  # NEW
    
    # ✅ Optional: Dashboard view
    path('dashboard/', retailer_dashboard_view, name='dashboard-view'),  # NEW



    # ✅ NEW: Order management
    path('orders/', RetailerOrderListView.as_view(), name='retailer-orders'),
    path('orders/<int:order_id>/', RetailerOrderDetailView.as_view(), name='retailer-order-detail'),
    
    # ✅ NEW: Payment history
    path('payments/', RetailerPaymentListView.as_view(), name='retailer-payments'),


    #================
    path(
        'retailer/profile/setup/',
        RetailerProfilePublicSetupView.as_view(),
        name='retailer-profile-public-setup'
    ),

    # ✅ ADDed 28th feb========================================\
    # path('profile/update/', RetailerProfileUpdateView.as_view(), name='retailer-profile-update'),
    path('retailers/', RetailerListView.as_view(), name='retailer-list'),
    path('retailers/<int:retailer_id>/', RetailerPublicDetailView.as_view(), name='retailer-public-detail'),
    #==========================================================/

     path('my-profile/', RetailerMyProfileView.as_view(), name='retailer-my-profile'),  # ✅ ADD THIS

     path('retailer/products/bulk-discount/', RetailerBulkDiscountView.as_view(), name='retailer-bulk-discount'),
     path('retailer/products/<int:product_id>/discount/', RetailerSingleProductDiscountView.as_view(), name='retailer-single-discount'),

]
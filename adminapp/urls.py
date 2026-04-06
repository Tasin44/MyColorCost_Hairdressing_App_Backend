from django.urls import path
from .views import (
    AdminDashboardStatsView,
    AdminUserListView,
    AdminRetailerListView,
    AdminRetailerApprovalView,
    AdminAffiliateUserListView,
    AdminOrderListView,
    AdminMissingProductListView,
    AdminMissingProductUpdateView,
    AdminUserDeleteView,
    AdminGrantFreeAccessView
)

urlpatterns = [
    # Dashboard stats
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    
    # Section 1: User management
    path('users/', AdminUserListView.as_view(), name='admin-user-list'),
    
    # Section 2: Retailer management
    path('retailers/', AdminRetailerListView.as_view(), name='admin-retailer-list'),
    path('retailers/<int:retailer_id>/approval/', AdminRetailerApprovalView.as_view(), name='admin-retailer-approval'),
    
    # Section 3: Affiliate users
    path('affiliates/', AdminAffiliateUserListView.as_view(), name='admin-affiliate-list'),
    
    # Section 4: Orders
    path('orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    
    # Section 5: Missing products
    path('missing-products/', AdminMissingProductListView.as_view(), name='admin-missing-products'),
    path('missing-products/<int:product_id>/', AdminMissingProductUpdateView.as_view(), name='admin-missing-product-update'),

    path("users/delete/", AdminUserDeleteView.as_view(), name="admin-user-delete"),
    path("users/free-access/", AdminGrantFreeAccessView.as_view(), name="admin-user-free-access"),
]
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from decimal import Decimal

User = get_user_model()

class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard overview statistics"""
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_users = serializers.IntegerField()
    total_subscribers = serializers.IntegerField()
    total_retailers = serializers.IntegerField()


class UserListSerializer(serializers.Serializer):
    """User list for admin"""
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    contact_number = serializers.CharField()
    role = serializers.CharField()
    staff_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class RetailerDetailSerializer(serializers.Serializer):
    """Detailed retailer information"""
    id = serializers.IntegerField()
    user_id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    contact_number = serializers.CharField()
    business_name = serializers.CharField()
    delivery_charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    free_delivery_threshold = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_orders = serializers.IntegerField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_pending = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_cancelled = serializers.IntegerField()
    api_key = serializers.CharField()
    is_approved = serializers.BooleanField()
    stripe_account_id = serializers.CharField()
    stripe_connected = serializers.BooleanField()
    stripe_connection_date = serializers.DateTimeField()
    created_at = serializers.DateTimeField()


class RetailerApprovalSerializer(serializers.Serializer):
    """Approve/reject retailer"""
    is_approved = serializers.BooleanField()
    admin_notes = serializers.CharField(required=False, allow_blank=True)


class AffiliateUserSerializer(serializers.Serializer):
    """Affiliate user statistics"""
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    referral_code = serializers.CharField()
    total_referrals = serializers.IntegerField()
    total_earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    withdrawn_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_balance = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderListSerializer(serializers.Serializer):
    """Order list for admin"""
    order_id = serializers.IntegerField()
    user_name = serializers.CharField()
    user_email = serializers.EmailField()
    order_date = serializers.DateTimeField()
    product_quantity = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()


class MissingProductRequestSerializer(serializers.Serializer):
    """User-requested products"""
    id = serializers.IntegerField()
    requested_by_name = serializers.CharField()
    requested_by_email = serializers.EmailField()
    product_name = serializers.CharField()
    category = serializers.CharField()
    brand = serializers.CharField()
    additional_notes = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
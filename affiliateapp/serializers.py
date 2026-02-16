
from rest_framework import serializers
from decimal import Decimal
from .models import ReferralCode, CommissionWithdrawal, Subscription


class ReferralCodeSerializer(serializers.ModelSerializer):
    """Serializer for referral code"""
    class Meta:
        model = ReferralCode
        fields = ['code', 'created_at']
        read_only_fields = ['code', 'created_at']


class ReferralStatsSerializer(serializers.Serializer):
    """Serializer for referral statistics"""
    total_referrals = serializers.IntegerField()
    active_referrals = serializers.IntegerField()
    total_commission_earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_commission = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_withdrawals = serializers.IntegerField()


class CommissionWithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for withdrawal requests"""
    class Meta:
        model = CommissionWithdrawal
        fields = [
            'id', 'amount', 'account_name', 'account_number',
            'bank_name', 'routing_number', 'bank_address',
            'status', 'admin_notes', 'created_at', 'processed_at'
        ]
        read_only_fields = ['id', 'status', 'admin_notes', 'created_at', 'processed_at']
    
    def validate_amount(self, value):
        user = self.context['request'].user
        if value > user.available_commission:
            raise serializers.ValidationError(
                f"Insufficient balance. Available: ${user.available_commission}"
            )
        if value < Decimal('10.00'):
            raise serializers.ValidationError("Minimum withdrawal amount is $10")
        return value


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for subscription data"""
    class Meta:
        model = Subscription
        fields = [
            'status', 'product_id', 'trial_end_date',
            'subscription_start_date', 'subscription_end_date',
            'subscription_amount', 'is_active'
        ]
        read_only_fields = fields
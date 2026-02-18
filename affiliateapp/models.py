from django.db import models
from django.conf import settings
from decimal import Decimal
from django.core.validators import MinValueValidator


class ReferralCode(models.Model):
    """Unique referral code for each user"""
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_code'
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        help_text="Unique referral code"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'referral_codes'
    
    def __str__(self):
        return f"{self.user.email} - {self.code}"


class Referral(models.Model):
    """Track referrals and commissions"""
    id = models.AutoField(primary_key=True)
    
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made',
        help_text="User who referred"
    )
    
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_by',
        help_text="User who was referred"
    )
    
    referral_code = models.ForeignKey(
        ReferralCode,
        on_delete=models.CASCADE,
        related_name='referrals'
    )
    
    # Commission tracking
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('25.00'),
        help_text="Commission percentage (25%)"
    )
    
    commission_earned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total commission earned from this referral"
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Subscription'),
        ('active', 'Active'),
        ('expired', 'Expired'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'referrals'
        unique_together = ('referrer', 'referred_user')
        indexes = [
            models.Index(fields=['referrer', 'status']),
            models.Index(fields=['referred_user']),
        ]


class Subscription(models.Model):
    """Track user subscriptions via RevenueCat"""
    id = models.AutoField(primary_key=True)
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    
    # RevenueCat data
    revenuecat_customer_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="RevenueCat customer ID"
    )
    
    product_id = models.CharField(
        max_length=100,
        help_text="Subscription product ID"
    )
    
    STATUS_CHOICES = (
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial'
    )
    
    # Subscription dates
    trial_end_date = models.DateTimeField(null=True, blank=True)
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    
    # Pricing (after Google Play fee - typically 15-30%)
    subscription_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subscription price"
    )
    
    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount after Google Play fees"
    )
    # ✅ ADD THIS NEW FIELD
    PLAN_CHOICES = (
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )
    plan_type = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='monthly',
        help_text="Subscription plan type"
    )
    
    
    # Tracking
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'


class CommissionWithdrawal(models.Model):
    """Track commission withdrawal requests"""
    id = models.AutoField(primary_key=True)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='withdrawal_requests'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('10.00'))],
        help_text="Withdrawal amount (minimum $10)"
    )
    
    # Bank details
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=255)
    routing_number = models.CharField(max_length=50, null=True, blank=True)
    bank_address = models.TextField(null=True, blank=True)
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    admin_notes = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'commission_withdrawals'
        ordering = ['-created_at']
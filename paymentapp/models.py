from django.db import models

# Create your models here.

from django.db import models
from django.conf import settings
from decimal import Decimal

class Payment(models.Model):
    """Track all payments"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    # Stripe data
    payment_intent_id = models.CharField(max_length=255, unique=True,        null=True,        # ✅ ADD THIS
    blank=True)       # ✅ ADD THIS)
    checkout_session_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Amounts
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Status
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        # ('refunded', 'Refunded'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Delivery address
    delivery_address = models.ForeignKey(
        'retailerapp.CustomerDeliveryAddress',
        on_delete=models.SET_NULL,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']


class PaymentRetailerSplit(models.Model):
    """Track payment splits to each retailer"""
    id = models.AutoField(primary_key=True)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='retailer_splits'
    )
    retailer = models.ForeignKey(
        'retailerapp.RetailerProfile',
        on_delete=models.CASCADE,
        related_name='payment_splits'
    )
    
    # Amounts
    product_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_share = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    platform_fee_share = models.DecimalField(max_digits=10, decimal_places=2)
    total_transfer_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Stripe transfer
    transfer_id = models.CharField(max_length=255, null=True, blank=True)
    transfer_status = models.CharField(max_length=20, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'payment_retailer_splits'
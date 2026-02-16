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


#====================================================================

class RetailerOrder(models.Model):
    """Individual order items per retailer"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        # ('processing', 'Processing'),
        # ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.AutoField(primary_key=True)
    
    # Links
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='retailer_orders'
    )
    retailer = models.ForeignKey(
        'retailerapp.RetailerProfile',
        on_delete=models.CASCADE,
        related_name='orders'
    )
    product = models.ForeignKey(
        'mixapp.ShopProduct',
        on_delete=models.CASCADE,
        related_name='orders'
    )
    
    # Order details
    product_name = models.CharField(max_length=255)  # Snapshot
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Delivery info (from CustomerDeliveryAddress)
    delivery_address_label = models.CharField(max_length=50)
    delivery_full_address = models.TextField()
    delivery_area = models.CharField(max_length=255)
    delivery_postal_code = models.CharField(max_length=20, null=True, blank=True)
    delivery_phone = models.CharField(max_length=20)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'retailer_orders'
        indexes = [
            models.Index(fields=['retailer', '-created_at']),
            models.Index(fields=['payment', 'retailer']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.id} - {self.product_name} x{self.quantity}"

'''
RetailerOrder model is NECESSARY. Here's why:

Why You NEED RetailerOrder Model:
Data Snapshot 📸

What if product price changes tomorrow?
What if product gets deleted?
Order must preserve historical data at time of purchase
Order-Specific Status 📦

Each order has its own lifecycle: pending → processing → shipped → delivered
You can't track this without a dedicated model
Delivery Information 🚚

Each order has specific delivery details
Can't dynamically fetch from Payment (payment has ONE address, but multiple retailer orders)
Retailer Needs This 🏪

Retailer must see:
"Which products did customer buy from ME?"
"Where to ship this specific item?"
"What's the status of each product?"
What Happens if You DON'T Create It:
❌ No way to track individual product status
❌ Can't answer: "Which orders are pending delivery?"
❌ Retailer can't manage their inventory/shipments
❌ No order history per product

Think of it like Amazon:
Payment = Customer paid once
RetailerOrder = Each item from different sellers (separate tracking numbers, separate delivery dates)
Conclusion: You MUST create RetailerOrder. It's not redundant—it's essential for order management. ✅
'''






























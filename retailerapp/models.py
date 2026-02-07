from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

class RetailerProfile(models.Model):
    """
    Extended profile for retailer users.
    Links to User model where role='retailer'
    """
    id = models.AutoField(primary_key=True)
    
    # ✅ One-to-One relationship with User
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='retailer_profile',
        db_index=True,
        help_text="Links to User with role='retailer'"
    )
    
    # ✅ Business Information
    business_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Official business/shop name"
    )
    
    # ✅ Delivery Configuration
    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        default=Decimal('0.00'),
        help_text="Standard delivery charge"
    )
    
    free_delivery_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        null=True,
        blank=True,
        help_text="Minimum order amount for free delivery"
    )
    
    # ✅ Business metrics (auto-calculated)
    total_orders = models.IntegerField(default=0)
    total_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_pending = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_cancelled = models.IntegerField(default=0)

    # ✅ ADD THESE STRIPE FIELDS
    stripe_account_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Stripe Connect account ID"
    )
    stripe_connected = models.BooleanField(
        default=False,
        help_text="Is Stripe onboarding complete?"
    )
    stripe_connection_date = models.DateTimeField(null=True, blank=True)
    
    # ✅ Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'retailer_profiles'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['business_name']),
        ]
    
    def __str__(self):
        return f"{self.business_name} ({self.user.email})"


class DeliveryArea(models.Model):
    """
    Delivery areas served by retailer.
    Each retailer can serve multiple areas.
    """
    id = models.AutoField(primary_key=True)
    
    # ✅ Link to retailer
    retailer = models.ForeignKey(
        RetailerProfile,
        on_delete=models.CASCADE,
        related_name='delivery_areas',
        db_index=True
    )
    
    # ✅ Area information
    area_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="e.g., Gulshan, Dhanmondi, Banani"
    )
    
    postal_code = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True
    )
    
    # ✅ Area-specific delivery charge (overrides default)
    custom_delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Leave blank to use retailer's default charge"
    )
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'delivery_areas'
        indexes = [
            models.Index(fields=['retailer', 'is_active']),
            models.Index(fields=['area_name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['retailer', 'area_name'],
                name='unique_retailer_area'
            )
        ]
    
    def __str__(self):
        return f"{self.area_name} - {self.retailer.business_name}"
    
    def get_delivery_charge(self):
        """Returns area-specific charge or retailer's default"""
        return self.custom_delivery_charge or self.retailer.delivery_charge


class MissingProduct(models.Model):
    """
    User-submitted requests for products not in catalog.
    Helps retailers understand demand.
    """
    id = models.AutoField(primary_key=True)
    
    # ✅ Who requested
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='missing_product_requests',
        db_index=True
    )
    
    # ✅ Product details (all text input by user)
    product_name = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True)
    additional_notes = models.TextField(null=True, blank=True)
    
    # ✅ Status tracking
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('added', 'Added to Catalog'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # ✅ If added, link to actual product
    added_product = models.ForeignKey(
        'mixapp.ShopProduct',  # Reference existing model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='missing_product_requests'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'missing_products'
        indexes = [
            models.Index(fields=['requested_by', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product_name} - {self.get_status_display()}"


class CustomerDeliveryAddress(models.Model):
    """
    Delivery addresses saved by customers.
    Each customer can have multiple addresses.
    """
    id = models.AutoField(primary_key=True)
    
    # ✅ Link to customer (owner/staff)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='delivery_addresses',
        db_index=True
    )
    
    # ✅ Address details
    address_label = models.CharField(
        max_length=50,
        help_text="e.g., Home, Office, Salon"
    )
    
    full_address = models.TextField()
    
    area = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Must match DeliveryArea.area_name for delivery"
    )
    
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    
    phone_number = models.CharField(max_length=20)
    
    # ✅ Quick access flag
    is_default = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        help_text="Default shipping address"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_delivery_addresses'
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['area']),
        ]
    
    def __str__(self):
        return f"{self.address_label} - {self.user.email}"
        




























from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

# Create your models here.
'''
What I Did in Code:
Only MAIN USER (salon owner) can purchase/add products to inventory.
Why This Makes Sense:

Financial Control 🏦

-Salon owner pays for products
-Owner controls inventory and expenses
-Staff shouldn't make purchasing decisions


Business Reality 💼

-In real salons, staff don't buy products
-Owner buys bulk inventory
-Staff just USE what's available


Simpler Inventory Management 📦

   UserProduct.objects.filter(user=main_user)  # Single inventory
   
   # If staff could buy:
   UserProduct.objects.filter(Q(user=owner) | Q(sub_user=staff))  # Complex!

Cost Tracking Clarity 💰

-All expenses under one account
-Easy profit calculation
-Clear financial reporting
'''
 
class ShopProduct(models.Model):
    """
    Master product catalog.
    Products that can be scanned and added to user inventory.
    """
    id = models.AutoField(primary_key=True)
 
    # Product information
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(null=True, blank=True)
 
    # Product media
    image = models.ImageField(
        upload_to='shop_products/',
        null=True,
        blank=True
    )
 
    # Pricing (market price per 100g)
    market_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Market price per 100g"
    )
 
    # Retailer information
    # retailer_name = models.CharField(max_length=255, null=True, blank=True)
 
    # Ratings
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_reviews = models.IntegerField(default=0)
 
    # Product identification
    barcode = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Barcode for scanning"
    )
 
    # Product metadata
    expiry_date = models.DateField(null=True, blank=True)
    stock_quantity = models.IntegerField(default=0) # deeps
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'shop_products'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['barcode']),
            models.Index(fields=['average_rating']),
        ]
        ordering = ['-created_at']
 
    def __str__(self):
        return f"{self.name} - {self.market_price}"
        # return f"{self.name} - {self.retailer_name or 'No Retailer'}"

    @property
    def in_stock(self):
        return self.stock_quantity > 0
    
    def update_rating(self):
        """
        Update average rating and review count.
        Should be called after adding/updating reviews.
        """
        from django.db.models import Avg, Count
 
        stats = self.reviews.aggregate(
            avg_rating=Avg('rating'),
            total=Count('id')
        )
 
        self.average_rating = stats['avg_rating'] or Decimal('0.00')
        self.total_reviews = stats['total']
        self.save(update_fields=['average_rating', 'total_reviews', 'updated_at'])
 
 
class UserProduct(models.Model):
    """
    User's product inventory after scanning.
    Tracks products owned by each user with their custom pricing.
    Inventory item — what each salon actually has in stock
    One UserProduct = one bottle/tube/pack in the salon
    """
    id = models.AutoField(primary_key=True)
 
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_products',
        db_index=True
    )
 
    product = models.ForeignKey(
        ShopProduct,
        on_delete=models.CASCADE,
        related_name='user_products',
        db_index=True
    )
 
    # User's custom price per 100g (can be different from market price)
    user_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="User's custom price per 100g"
    )
 
    # Current available weight in grams
    current_weight_grams = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Available weight in grams"
    )
 
    # Availability flag
    is_available = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Is product currently available for use"
    )
 
    # Timestamps
    scanned_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        db_table = 'user_products'
        indexes = [
            models.Index(fields=['user', 'is_available']),
            models.Index(fields=['user', 'product']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_product'
            )
        ]
        ordering = ['-scanned_at']
 
    def __str__(self):
        return f"{self.user.email} - {self.product.name} - {self.current_weight_grams}g left"
 
    def reduce_weight(self, used_weight):
        """
        Reduce product weight after use in a mix.
        """
        self.current_weight_grams -= Decimal(str(used_weight))
 
        # Mark as unavailable if weight is 0 or negative
        if self.current_weight_grams <= 0:
            self.current_weight_grams = Decimal('0.00')
            self.is_available = False
 
        self.last_used_at = models.DateTimeField(auto_now=True)
        self.save(update_fields=['current_weight_grams', 'is_available', 'last_used_at'])
 
class ShoppingCart(models.Model):
    """Shopping cart for purchasing products"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart_items',
        db_index=True
    )
    shop_product = models.ForeignKey(
        ShopProduct,
        on_delete=models.CASCADE,
        related_name='cart_items',
        db_index=True
    )
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'added_at']),
        ]
        unique_together = [['user', 'shop_product']]
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.shop_product.name} x{self.quantity}"
    
    @property
    def total_price(self):
        return self.shop_product.price * self.quantity


class ProductScanHistory(models.Model):
    """History of product scans"""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='scan_history',
        db_index=True
    )
    shop_product = models.ForeignKey(
        ShopProduct,
        on_delete=models.CASCADE,
        related_name='scan_history',
        db_index=True
    )
    
    # Scan details
    barcode = models.CharField(max_length=100, null=True, blank=True)
    qr_code = models.CharField(max_length=100, null=True, blank=True)
    scanned_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Location data (optional)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    scan_type = models.CharField(max_length=20, choices=[
        ('barcode', 'Barcode'),
        ('qr', 'QR Code'),
        ('manual', 'Manual Entry'),
    ], default='barcode')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['shop_product', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} scanned {self.shop_product.name}"
    

class ProductReview(models.Model):
    """
    User reviews for shop products.
    """
    id = models.AutoField(primary_key=True)
 
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_reviews',
        db_index=True
    )
 
    product = models.ForeignKey(
        ShopProduct,
        on_delete=models.CASCADE,
        related_name='reviews',
        db_index=True
    )
 
    # Review details
    rating = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Rating between 1 and 5"
    )
 
    review_text = models.TextField(null=True, blank=True)
 
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'product_reviews'
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['user']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_product_review'
            ),
            models.CheckConstraint(
                check=models.Q(rating__gte=1, rating__lte=5),
                name='rating_range_check'
            )
        ]
        ordering = ['-created_at']
 
    def __str__(self):
        return f"{self.user.email} - {self.product.name} ({self.rating}★)"
 

from django.db import models

# Create your models here.
# mixapp/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from authapp.models import SubUser
from clientapp.models import Client
 
#======================================================================================================================================================================
#================================================================================productapp============================================================================


# from django.db import models
# from django.conf import settings
# from django.core.validators import MinValueValidator
# from decimal import Decimal

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
    #My thinking-Scanned product will be added here
    
    id = models.AutoField(primary_key=True)

    # ✅ ADD THIS NEW FIELD
    api_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Full API response from Barcode Spider"
    )

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

    #===========================================================\
    # ✅ ADD THESE
    discounted_market_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Price after discount. None means no discount active"
    )
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    #=============================================================/
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
 
     # ✅ ADD THESE NEW FIELDS
    retailer = models.ForeignKey(
        'retailerapp.RetailerProfile',  # Link to retailer
        on_delete=models.CASCADE,
        related_name='products',
        null=True,  # Nullable for backward compatibility
        blank=True,
        db_index=True,
        help_text="Retailer selling this product"
    )
    
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Available stock quantity"
    )
    
    STOCK_STATUS_CHOICES = (
        ('in_stock', 'In Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('low_stock', 'Low Stock'),
    )
    stock_status = models.CharField(
        max_length=20,
        choices=STOCK_STATUS_CHOICES,
        default='in_stock',
        db_index=True
    )
    # ✅ ADDed 28th feb
    vat = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        help_text="VAT percentage (e.g., 15.00 means 15%)"
    )

    #======================================================================================\
    # ✅ Buy X Get Y Free promo fields
    promo_buy_quantity = models.IntegerField(
        null=True, blank=True,
        help_text="Buy this many (e.g. 5 for buy-5-get-1-free)"
    )
    promo_free_quantity = models.IntegerField(
        null=True, blank=True,
        help_text="Get this many free (e.g. 1 for buy-5-get-1-free)"
    )
    promo_is_active = models.BooleanField(
        default=False,
        help_text="Is this promo currently active?"
    )

    #======================================================================================/
    # ✅ Auto-update stock_status based on quantity
    def save(self, *args, **kwargs):
        # Auto-set stock_status based on quantity
        if self.quantity == 0:
            self.stock_status = 'out_of_stock'
        elif self.quantity <= 10:  # Low stock threshold
            self.stock_status = 'low_stock'
        else:
            self.stock_status = 'in_stock'
        
        super().save(*args, **kwargs)
    
    # ✅ ADD THIS PROPERTY
    @property
    def retailer_name(self):
        """Returns retailer business name or 'Unknown'"""
        return self.retailer.business_name if self.retailer else 'Unknown'

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
    """

    #Remember, UserProduct model only will contains the product after scanning, not the product what the use purchesed, because product user purchesed, it has to first come to his hand 

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
 
    # User's custom price for the whole product, not for 100gm
    user_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="User's custom price per 100g",
        null=True,  # ✅ ADD THIS
        blank=True  # ✅ ADD THIS
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
    original_weight_grams = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Original weight when product was first added"
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
 
        # self.last_used_at = models.DateTimeField(auto_now=True)❌❌❌is a FIELD DEFINITION, not a value,It's meant to be used in the model class definition,It creates a Field object, not a datetime value

        self.last_used_at = timezone.now()  # ✅ FIX: Use timezone.now(), not DateTimeField
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
        return self.shop_product.market_price * self.quantity


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
    
    # # Location data (optional)
    # latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
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
        '''
        #Error : TypeError: CheckConstraint.__init__() got an unexpected keyword argument 'check'
        ❌ Why this error is coming
        You are using an old Django version that does NOT support CheckConstraint(check=...).

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
    
        '''

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_product_review'
            )
        ]
        ordering = ['-created_at']
 
    def __str__(self):
        return f"{self.user.email} - {self.product.name} ({self.rating}★)"
 



#=========================================================Mixapp===========================================================================================================
#==========================================================================================================================================================================


class Mix(models.Model):
    """
    Color bowl/mix created for a client.
    Contains multiple products and tracks costs.
    """
    id = models.AutoField(primary_key=True)
 
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mixes',
        db_index=True,
        help_text="Salon owner"
    )
 
    sub_user = models.ForeignKey(
        SubUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mixes',
        db_index=True,
        help_text="Staff member who created (if applicable)"
    )
 
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='mixes',
        db_index=True,
        null=True,
        blank=True,
        help_text="Client this mix is for"
    )
 
    # Mix details
    mix_name = models.CharField(max_length=255, db_index=True)
    service_type = models.CharField(max_length=100, db_index=True)

    # NEW: FK to ServiceType for new mix creation flow (nullable for backward compat)
    service_type_fk = models.ForeignKey(
        'appointmentapp.ServiceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mixes',
        help_text="FK to ServiceType (used by new mix creation API)"
    )
 
    # Financial tracking
    charged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount charged to client"
    )
 
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total cost of products used"
    )
 
    # Profit calculation (will be calculated in save method)
    profit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Profit = charged_amount - total_cost"
    )
 
    # Creation tracking
    created_date = models.DateField(db_index=True)
    created_time = models.TimeField()
 
    # PDF export
    pdf_url = models.CharField(max_length=500, null=True, blank=True)
 
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'mixes'
        indexes = [
            models.Index(fields=['user', 'created_date']),
            models.Index(fields=['client', 'created_date']),
            models.Index(fields=['service_type']),
            models.Index(fields=['-created_date', '-created_time']),
        ]
        ordering = ['-created_date', '-created_time']
 
    def __str__(self):
        client_name = self.client.name if self.client else "No Client"
        return f"{self.mix_name} - {client_name} ({self.created_date})"
 
    def calculate_total_cost(self):
        """
        Calculate total cost from all mix products.
        Should be called after adding/updating products.
        """
        from django.db.models import Sum
 
        total = self.mix_products.aggregate(
            total=Sum('each_item_cost')
        )['total'] or Decimal('0.00')
 
        self.total_cost = total
        self.calculate_profit()
        # ✅ Only update specific fields, don't trigger MixProduct saves
        self.save(update_fields=['total_cost', 'profit', 'updated_at'])
 
    def calculate_profit(self):
        """Calculate profit (charged - cost)"""
        if self.charged_amount:
            self.profit = self.charged_amount - self.total_cost
        else:
            self.profit = Decimal('0.00')
 
    def save(self, *args, **kwargs):
        """Override save to auto-calculate profit"""
        if not self.pk:
            now = timezone.now()
            self.created_date = now.date()
            self.created_time = now.time()
        if self.charged_amount is not None:
            self.calculate_profit()
        super().save(*args, **kwargs)
 
 
class MixProduct(models.Model):
    """
    Individual products used in a mix with quantities and costs.
    """
    id = models.AutoField(primary_key=True)
 
    # Relationships
    mix = models.ForeignKey(
        Mix,
        on_delete=models.CASCADE,
        related_name='mix_products',
        db_index=True
    )
 
    user_product = models.ForeignKey(
        UserProduct,
        on_delete=models.CASCADE,
        related_name='mix_products',
        db_index=True
    )
 
    # Product snapshot (stored to preserve history even if product changes)
    product_name = models.CharField(max_length=255)
 
    # Usage details
    used_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Weight used in grams"
    )
 
    # Pricing snapshot at time of use
    market_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Market price per 100g at time of use"
    )
 
    user_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="User's price per 100g at time of use"
    )
 
    # Cost calculation: (user_price * used_weight) / 100
    each_item_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cost for this item"
    )
 
    # Bleach timer (for bleach products)
    # bleach_timer_started_at = models.DateTimeField(
    #     null=True,
    #     blank=True,
    #     help_text="When bleach timer was started"
    # )
    is_bleach_timer_on = models.BooleanField(default=True)
    # bleach_timer_started_at = models.CharField(  # ✅ Changed to CharField
    #     max_length=50,
    #     null=True,
    #     blank=True,
    #     editable=True  # Add this
    # )
    bleach_timer_start_time = models.CharField(  # NEW NAME
        max_length=50,
        null=True,
        blank=True
    )
    
    bleach_timer_duration = models.CharField(   # ✅ NEW
        max_length=30,
        null=True,
        blank=True,
        help_text="e.g. 30 min, 1 hour"
    )
    class Meta:
        db_table = 'mix_products'
        indexes = [
            models.Index(fields=['mix']),
            models.Index(fields=['user_product']),
        ]
        ordering = ['id']
 
    def __str__(self):
        return f"{self.product_name} - {self.used_weight}g in {self.mix.mix_name}"
 
    def calculate_cost(self):
        """
        Calculate cost based on used weight and user price.
        Formula: (user_price * used_weight) / 100
        """
        self.each_item_cost = (
            self.user_price * self.used_weight
        ) / Decimal('100')
 
    # def calculate_cost(self):
    #     # user_price = total price user paid for the product
    #     # current_weight_grams = weight BEFORE this usage (since reduce_weight runs after)
    #     total_weight = self.user_product.current_weight_grams
    #     if total_weight > 0:
    #         price_per_gram = self.user_price / total_weight
    #         self.each_item_cost = (price_per_gram * self.used_weight).quantize(Decimal('0.01'))
    #     else:
    #         self.each_item_cost = Decimal('0.00')

    # def save(self, *args, **kwargs):
    #     # if not self.pk and not self.bleach_timer_started_at:
    #     #     self.bleach_timer_started_at = timezone.now().isoformat()
    #     self.calculate_cost()
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.each_item_cost:  # Only calculate if not already set
            self.calculate_cost()
        super().save(*args, **kwargs)


# =============================================================================
# NEW: Bowl and BowlProduct models for new mix creation flow
# The existing Mix/MixProduct models above are completely untouched.
# =============================================================================

class Bowl(models.Model):
    """
    A "bowl" within a Mix — each bowl can hold multiple products.
    One Mix can have many Bowls.
    This replaces the flat Mix → MixProduct structure for the new API.
    """
    id = models.AutoField(primary_key=True)

    mix = models.ForeignKey(
        Mix,
        on_delete=models.CASCADE,
        related_name='bowls',
        db_index=True,
        help_text="Parent mix this bowl belongs to"
    )

    service_name = models.CharField(
        max_length=255,
        help_text="e.g. Hair Color Service"
    )
    mix_name = models.CharField(
        max_length=255,
        help_text="e.g. Spa Mix 14"
    )
    charged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount charged for this bowl"
    )
    bleach_timer_start_time = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="ISO datetime string for bleach timer"
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Sum of all product costs in this bowl"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bowls'
        ordering = ['id']

    def __str__(self):
        return f"Bowl: {self.mix_name} in Mix#{self.mix_id}"

    def calculate_total_cost(self):
        """Sum BowlProduct costs and save."""
        from django.db.models import Sum
        total = self.bowl_products.aggregate(
            total=Sum('each_item_cost')
        )['total'] or Decimal('0.00')
        self.total_cost = total
        self.save(update_fields=['total_cost', 'updated_at'])


class BowlProduct(models.Model):
    """
    A product used inside a Bowl.
    Mirrors MixProduct but belongs to Bowl instead of Mix.
    """
    id = models.AutoField(primary_key=True)

    bowl = models.ForeignKey(
        Bowl,
        on_delete=models.CASCADE,
        related_name='bowl_products',
        db_index=True
    )
    user_product = models.ForeignKey(
        UserProduct,
        on_delete=models.CASCADE,
        related_name='bowl_products',
        db_index=True
    )

    product_name = models.CharField(max_length=255)
    used_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Weight used in grams"
    )
    market_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Market price per 100g at time of use"
    )
    user_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="User’s price per 100g at time of use"
    )
    each_item_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cost for this item: (user_price / original_weight) * used_weight"
    )

    class Meta:
        db_table = 'bowl_products'
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} – {self.used_weight}g in {self.bowl}"

    def calculate_cost(self):
        """(user_price * used_weight) / 100"""
        self.each_item_cost = (
            self.user_price * self.used_weight
        ) / Decimal('100')

    def save(self, *args, **kwargs):
        if not self.each_item_cost:
            self.calculate_cost()
        super().save(*args, **kwargs)




#=================================================================
#Expense 
from django.db import models


class Expense(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expenses')
    expense_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='expenses/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.expense_name

























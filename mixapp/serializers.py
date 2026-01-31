# mixapp/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator
from .models import ShopProduct, UserProduct, Mix, MixProduct, ProductReview,ShoppingCart
from clientapp.models import Client
 
#================================================productapp-serializers.py==========================================================================================
#===================================================================================================================================================================

class ShopProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product listings"""
    image_url = serializers.SerializerMethodField()
 
    class Meta:
        model = ShopProduct
        fields = [
            'id', 'name', 'image_url', 'market_price', 'average_rating', 'total_reviews'
        ]
 
    def get_image_url(self, obj):
        """Get absolute URL for product image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
 
 
class ShopProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single product view"""
    image_url = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = ShopProduct
        fields = [
            'id', 'name', 'description', 'image_url',
            'market_price', 'average_rating',
            'total_reviews', 'barcode', 'stock_quantity','in_stock','expiry_date', 'created_at','api_data'  # ✅ ADD THIS
        ]
 
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
 
 
class UserProductSerializer(serializers.ModelSerializer):
    """Serializer for user's product inventory"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    market_price = serializers.DecimalField(
        source='product.market_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    scanned_at = serializers.SerializerMethodField()  # ✅ CHANGE TO METHOD FIELD
 
    class Meta:
        model = UserProduct
        fields = [
            'id', 'product', 'product_name', 'product_image',
            'market_price', 'user_price', 'current_weight_grams',
            'is_available', 'scanned_at', 'last_used_at'
        ]
        read_only_fields = ['id', 'last_used_at']
 
    def get_product_image(self, obj):
        """Get product image URL"""
        if obj.product.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.product.image.url)
            return obj.product.image.url
        return None
    # ✅ ADD THIS METHOD
    def get_scanned_at(self, obj):
        """Only show scanned_at if not manual entry"""
        # Check if this is manual entry context
        is_manual_entry = self.context.get('is_manual_entry', False)
        
        if is_manual_entry:
            return None  # Don't return for manual entries
        
        return obj.scanned_at.isoformat() if obj.scanned_at else None
 
class CreateUserProductSerializer(serializers.ModelSerializer):
    """Serializer for adding product to user inventory"""
    product_id = serializers.IntegerField(write_only=True)
 
    class Meta:
        model = UserProduct
        fields = ['product_id', 'user_price', 'current_weight_grams']
        extra_kwargs = {
            'user_price': {'required': False}  # ✅ MAKE OPTIONAL
        }
 
    def validate_product_id(self, value):
        """Validate product exists"""
        try:
            ShopProduct.objects.get(id=value)
        except ShopProduct.DoesNotExist:
            raise serializers.ValidationError("Product not found")
        return value
 
    def validate_user_price(self, value):
        """Validate user price is positive"""
        #if value <= 0:
        if value is not None and value <= 0:  # ✅ ADD NULL CHECK
            raise serializers.ValidationError("Price must be greater than 0")
        return value
 
    def validate_current_weight_grams(self, value):
        """Validate weight is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Weight cannot be negative")
        return value
 
    @transaction.atomic
    def create(self, validated_data):
        """Create or update user product"""
        user = self.context['request'].user
        product_id = validated_data.pop('product_id')
        product = ShopProduct.objects.get(id=product_id)
 
        # Check if product already exists for user
        user_product, created = UserProduct.objects.get_or_create(
            user=user,
            product=product,
            defaults={
                'user_price': validated_data.get('user_price'),
                'current_weight_grams': validated_data['current_weight_grams'],
                'is_available': validated_data['current_weight_grams'] > 0
            }
        )
 
        # If not created, update existing
        if not created:
            # user_product.user_price = validated_data['user_price']
            if 'user_price' in validated_data:  # ✅ ONLY UPDATE IF PROVIDED
                user_product.user_price = validated_data['user_price']
            user_product.current_weight_grams += validated_data['current_weight_grams']
            user_product.is_available = user_product.current_weight_grams > 0
            user_product.save(update_fields=[
                'user_price', 'current_weight_grams', 'is_available'
            ])
 
        return user_product
 



class ShoppingCartSerializer(serializers.ModelSerializer):
    shop_product = ShopProductDetailSerializer(read_only=True)
    shop_product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    product_name = serializers.CharField(source='shop_product.name', read_only=True)
    product_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ShoppingCart
        fields = [
            'id', 'shop_product', 'shop_product_id', 'quantity',
            'total_price', 'product_name', 'product_image_url',
            'added_at'
        ]
        read_only_fields = ['id', 'total_price', 'product_name', 'product_image_url', 'added_at']
    
    def get_product_image_url(self, obj):
        if obj.shop_product.image:
            return obj.shop_product.image.url
        return None
    
    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError('Quantity must be at least 1.')
        return value


class ScanProductSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=100, required=False)
    qr_code = serializers.CharField(max_length=100, required=False)
    product_id = serializers.IntegerField(required=False)
    scanned_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        validators=[MinValueValidator(0)]
    )
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    
    def validate(self, data):
        # At least one identifier must be provided
        identifiers = ['barcode', 'qr_code', 'product_id']
        if not any(data.get(identifier) for identifier in identifiers):
            raise serializers.ValidationError(
                'Provide at least one of: barcode, qr_code, or product_id'
            )
        return data


class ProductSearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    min_rating = serializers.DecimalField(max_digits=3, decimal_places=2, required=False)
    retailer = serializers.CharField(required=False)
    in_stock = serializers.BooleanField(required=False)
    page = serializers.IntegerField(default=1, min_value=1)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)


class InventoryStatsSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    available_products = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    bleach_products = serializers.IntegerField()
    total_inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    category_distribution = serializers.DictField()





#=========================================================Mixapp===========================================================================================================
#==========================================================================================================================================================================
class MixProductSerializer(serializers.ModelSerializer):
    """Serializer for products within a mix"""
    # # bleach_timer_started_at = serializers.DateTimeField(
    # #     format='%Y-%m-%d %H:%M:%S',  # or use iso-8601 format
    # #     required=False,
    # #     allow_null=True
    # # )
    # bleach_timer_started_at = serializers.SerializerMethodField()
    class Meta:
        model = MixProduct
        fields = [
            'id', 'product_name', 'used_weight', 'market_price',
            'user_price', 'each_item_cost','is_bleach_timer_on','bleach_timer_start_time','bleach_timer_duration'
        ]
        read_only_fields = ['id', 'each_item_cost']
 
    # def get_bleach_timer_started_at(self, obj):
    #     return obj.bleach_timer_started_at.isoformat() if obj.bleach_timer_started_at else None
    
class AddProductToMixSerializer(serializers.Serializer):
    """Serializer for adding a product to a mix"""
    user_product_id = serializers.IntegerField()
    used_weight = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    #start_bleach_timer = serializers.BooleanField(default=False)
    market_price = serializers.DecimalField(max_digits=10, decimal_places=2,
    required=False,  # ✅ ADD THIS
    allow_null=True  # ✅ ADD THIS
    )

    user_price = serializers.DecimalField(  # ✅ ADD THIS FIELD
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01')
    )



    #charged_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    #bleach_timer_start_time = serializers.CharField(required=False,
   # allow_null=True)
    # ✅ Be MORE explicit - don't let DRF auto-detect
    bleach_timer_start_time = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,  # Add this
        max_length=50      # Add this
    )
    # is_bleach_timer_on = serializers.BooleanField()
    # bleach_timer_duration = serializers.CharField(   # ✅ ADD
    #     required=False,
    #     allow_null=True
    # )
    is_bleach_timer_on = serializers.BooleanField(default=False)  # Add default
    bleach_timer_duration = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,  # Add this
        max_length=30      # Add this
    )
    def validate_user_product_id(self, value):
        """Validate user product exists and is available"""
        user = self.context['request'].user
        # ✅ FIX: Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        try:
            #user_product = UserProduct.objects.get(id=value, user=user)
            user_product = UserProduct.objects.get(id=value, user=owner)
        except UserProduct.DoesNotExist:
            raise serializers.ValidationError("Product not found in your inventory")
 
        if not user_product.is_available:
            raise serializers.ValidationError("This product is not available")
 
        return value
 
    # def validate(self, data):
    #     """Validate sufficient weight is available"""
    #     user = self.context['request'].user
    #     user_product = UserProduct.objects.get(
    #         id=data['user_product_id'],
    #         user=user
    #     )
 
    #     if user_product.current_weight_grams < data['used_weight']:
    #         raise serializers.ValidationError({
    #             'used_weight': f"Insufficient weight. Available: {user_product.current_weight_grams}g"
    #         })
 
    #     data['user_product'] = user_product
    #     return data
    def validate(self, data):
        """Validate sufficient weight is available"""
        user = self.context['request'].user
        
        # ✅ FIX: Use same owner logic as validate_user_product_id
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        try:
            user_product = UserProduct.objects.get(
                id=data['user_product_id'],
                user=owner  # ✅ Use owner instead of user
            )
        except UserProduct.DoesNotExist:
            raise serializers.ValidationError({
                'user_product_id': "Product not found in inventory"
            })
 
        if user_product.current_weight_grams < data['used_weight']:
            raise serializers.ValidationError({
                'used_weight': f"Insufficient weight. Available: {user_product.current_weight_grams}g"
            })
 
        data['user_product'] = user_product
        return data
 
class MixListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for mix listings"""
    client_name = serializers.CharField(source='client.name', read_only=True)
    product_count = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
 
    class Meta:
        model = Mix
        fields = [
            'id', 'mix_name', 'client_name', 'service_type',
            'total_cost', 'charged_amount', 'profit',
            'created_date', 'created_time', 'product_count',
            'created_by'
        ]
 
    def get_product_count(self, obj):
        """Get number of products in mix"""
        # Use prefetch_related in view to avoid N+1
        if hasattr(obj, 'mix_products'):
            return obj.mix_products.count()
        return 0
 
    def get_created_by(self, obj):
        """Return who created the mix"""
        if obj.sub_user:
            return {
                'type': 'staff',
                'name': obj.sub_user.name,
                #'id': obj.sub_user.id,      # ✅ Get User ID, not SubUser ID
                'id': obj.sub_user.user.id,  # ✅ CHANGED: Get the actual User ID
                'email': obj.sub_user.email       # Optional: add email
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email,
            'id': obj.user.id,
            'email': obj.user.email
        }
 
 
class MixDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single mix view"""
    client_name = serializers.CharField(source='client.name', read_only=True)
    # client_id = serializers.IntegerField(source='client.id', read_only=True)
    products = MixProductSerializer(source='mix_products', many=True, read_only=True)
    created_by = serializers.SerializerMethodField()
 
    class Meta:
        model = Mix
        fields = [
            'id', 'mix_name', 'client_name',
            'service_type', 'charged_amount', 'total_cost',
            'profit', 'created_date', 'created_time',
            'pdf_url', 'products', 'created_by', 'created_at'
        ]
 
    def get_created_by(self, obj):
        """Return who created the mix"""
        if obj.sub_user:
            return {
                'type': 'staff',
                'name': obj.sub_user.name,
                'id': obj.sub_user.user.id,  # ✅ CHANGED: Get the actual User ID
                'email': obj.sub_user.email
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email,
            'id': obj.user.id,
            'email': obj.user.email
        }

 
class CreateMixSerializer(serializers.ModelSerializer):
    """Serializer for creating a new mix"""
    # client_id = serializers.IntegerField(write_only=True)
    created_date = serializers.SerializerMethodField()
    created_time = serializers.SerializerMethodField()

    class Meta:
        model = Mix
        fields = [
            'mix_name', 'service_type', 'created_date', 'created_time'
        ]
    
    '''
    def validate_client_id(self, value):
        user = self.context['request'].user
        try:
            Client.objects.get(id=value, user=user)
        except Client.DoesNotExist:
            raise serializers.ValidationError("Client not found")
 
        return value
    '''

 
    def validate_mix_name(self, value):
        """Validate mix name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Mix name is required")
        return value.strip()
 
    # def validate_charged_amount(self, value):
    #     """Validate charged amount if provided"""
    #     if value is not None and value < 0:
    #         raise serializers.ValidationError("Charged amount cannot be negative")
    #     return value

    def get_created_date(self, obj):
        return obj.created_at.date()

    def get_created_time(self, obj):
        return obj.created_at.time()
    
    @transaction.atomic
    def create(self, validated_data):
        """Create mix"""
        user = self.context['request'].user
        #client_id = validated_data.pop('client_id')
      #  client = Client.objects.get(id=client_id)
 
        # Create mix
        mix = Mix.objects.create(
            user=user,
            sub_user=None,  # Set if request from staff
            #client=client,
            **validated_data
        )
 
        return mix
 
 
class UpdateMixSerializer(serializers.ModelSerializer):
    """Serializer for updating mix details"""
 
    class Meta:
        model = Mix
        # fields = ['mix_name', 'service_type', 'charged_amount']
        fields = ['mix_name', 'service_type']
 
    def validate_charged_amount(self, value):
        """Validate charged amount"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Charged amount cannot be negative")
        return value
 
 
class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for product reviews"""
    user_name = serializers.CharField(source='user.name', read_only=True)
 
    class Meta:
        model = ProductReview
        fields = [
            'id', 'user_name', 'rating', 'review_text',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
 
 
class CreateProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for creating product review"""
    product_id = serializers.IntegerField(write_only=True)
 
    class Meta:
        model = ProductReview
        fields = ['product_id', 'rating', 'review_text']
 
    def validate_product_id(self, value):
        """Validate product exists"""
        try:
            ShopProduct.objects.get(id=value)
        except ShopProduct.DoesNotExist:
            raise serializers.ValidationError("Product not found")
        return value
 
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
 
    @transaction.atomic
    def create(self, validated_data):
        """Create or update review"""
        user = self.context['request'].user
        product_id = validated_data.pop('product_id')
        product = ShopProduct.objects.get(id=product_id)
 
        # Create or update review
        review, created = ProductReview.objects.update_or_create(
            user=user,
            product=product,
            defaults=validated_data
        )
 
        # Update product rating
        product.update_rating()
 
        return review
 
 
class MixStatsSerializer(serializers.Serializer):
    """Serializer for mix statistics"""
    total_mixes = serializers.IntegerField()
    total_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    mixes_this_month = serializers.IntegerField()
    most_used_service_type = serializers.CharField()
 

class AssignClientSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()

class SetChargedAmountSerializer(serializers.Serializer):
    charged_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01')
    )


#-------------------------------------------------------------------------------------------------------------
class BarcodeScanRequestSerializer(serializers.Serializer):
    """Serializer for barcode scan request"""
    barcode = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Scanned barcode/UPC"
    )
    
    def validate_barcode(self, value):
        """Validate barcode format"""
        if not value or not value.strip():
            raise serializers.ValidationError("Barcode cannot be empty")
        return value.strip()


class BarcodeScanResponseSerializer(serializers.Serializer):
    """Serializer for barcode scan response"""
    found_in_db = serializers.BooleanField()
    found_in_api = serializers.BooleanField()
    manual_entry_required = serializers.BooleanField()
    product = serializers.SerializerMethodField()
    message = serializers.CharField()
    
    def get_product(self, obj):
        """Return product data if available"""
        product_data = obj.get('product')
        if product_data:
            # If it's a ShopProduct instance
            if hasattr(product_data, 'id'):
                return ShopProductDetailSerializer(product_data, context=self.context).data
            # If it's dict from API
            return product_data
        return None


class ManualProductEntrySerializer(serializers.Serializer):
    """Serializer for manual product entry"""
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    market_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=True
    )
    current_weight_grams = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=True
    )
    barcode = serializers.CharField(max_length=100, required=False, allow_blank=True)
    image = serializers.ImageField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    
    def validate_name(self, value):
        """Validate product name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Product name is required")
        return value.strip()


class UpdateScannedProductSerializer(serializers.Serializer):
    """Update scanned product with manual price and weight"""
    market_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False
    )
    current_weight_grams = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False
    )
    user_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        help_text="Optional: User's custom price per 100g"
    )
    
    def validate(self, data):
        """At least one field must be provided"""
        if not any(data.values()):
            raise serializers.ValidationError(
                "At least one of market_price, current_weight_grams, or user_price must be provided"
            )
        return data





















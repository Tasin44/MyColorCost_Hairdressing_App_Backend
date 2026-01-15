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
            'total_reviews', 'barcode', 'stock_quantity','in_stock','expiry_date', 'created_at'
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
 
    class Meta:
        model = UserProduct
        fields = [
            'id', 'product', 'product_name', 'product_image',
            'market_price', 'user_price', 'current_weight_grams',
            'is_available', 'scanned_at', 'last_used_at'
        ]
        read_only_fields = ['id', 'scanned_at', 'last_used_at']
 
    def get_product_image(self, obj):
        """Get product image URL"""
        if obj.product.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.product.image.url)
            return obj.product.image.url
        return None
 
 
class CreateUserProductSerializer(serializers.ModelSerializer):
    """Serializer for adding product to user inventory"""
    product_id = serializers.IntegerField(write_only=True)
 
    class Meta:
        model = UserProduct
        fields = ['product_id', 'user_price', 'current_weight_grams']
 
    def validate_product_id(self, value):
        """Validate product exists"""
        try:
            ShopProduct.objects.get(id=value)
        except ShopProduct.DoesNotExist:
            raise serializers.ValidationError("Product not found")
        return value
 
    def validate_user_price(self, value):
        """Validate user price is positive"""
        if value <= 0:
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
                'user_price': validated_data['user_price'],
                'current_weight_grams': validated_data['current_weight_grams'],
                'is_available': validated_data['current_weight_grams'] > 0
            }
        )
 
        # If not created, update existing
        if not created:
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
 
    class Meta:
        model = MixProduct
        fields = [
            'id', 'product_name', 'used_weight', 'market_price',
            'user_price', 'each_item_cost', 'bleach_timer_started_at'
        ]
        read_only_fields = ['id', 'each_item_cost']
 
 
class AddProductToMixSerializer(serializers.Serializer):
    """Serializer for adding a product to a mix"""
    user_product_id = serializers.IntegerField()
    used_weight = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    start_bleach_timer = serializers.BooleanField(default=False)
 
    def validate_user_product_id(self, value):
        """Validate user product exists and is available"""
        user = self.context['request'].user
 
        try:
            user_product = UserProduct.objects.get(id=value, user=user)
        except UserProduct.DoesNotExist:
            raise serializers.ValidationError("Product not found in your inventory")
 
        if not user_product.is_available:
            raise serializers.ValidationError("This product is not available")
 
        return value
 
    def validate(self, data):
        """Validate sufficient weight is available"""
        user = self.context['request'].user
        user_product = UserProduct.objects.get(
            id=data['user_product_id'],
            user=user
        )
 
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
                'name': obj.sub_user.name
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email
        }
 
 
class MixDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single mix view"""
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_id = serializers.IntegerField(source='client.id', read_only=True)
    products = MixProductSerializer(source='mix_products', many=True, read_only=True)
    created_by = serializers.SerializerMethodField()
 
    class Meta:
        model = Mix
        fields = [
            'id', 'mix_name', 'client_id', 'client_name',
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
                'id': obj.sub_user.id
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email,
            'id': obj.user.id
        }
 
 
class CreateMixSerializer(serializers.ModelSerializer):
    """Serializer for creating a new mix"""
    client_id = serializers.IntegerField(write_only=True)
 
    class Meta:
        model = Mix
        fields = [
            'mix_name', 'client_id', 'service_type',
            'charged_amount', 'created_date', 'created_time'
        ]
 
    def validate_client_id(self, value):
        """Validate client exists and belongs to user"""
        user = self.context['request'].user
 
        try:
            Client.objects.get(id=value, user=user)
        except Client.DoesNotExist:
            raise serializers.ValidationError("Client not found")
 
        return value
 
    def validate_mix_name(self, value):
        """Validate mix name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Mix name is required")
        return value.strip()
 
    def validate_charged_amount(self, value):
        """Validate charged amount if provided"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Charged amount cannot be negative")
        return value
 
    @transaction.atomic
    def create(self, validated_data):
        """Create mix"""
        user = self.context['request'].user
        client_id = validated_data.pop('client_id')
        client = Client.objects.get(id=client_id)
 
        # Create mix
        mix = Mix.objects.create(
            user=user,
            sub_user=None,  # Set if request from staff
            client=client,
            **validated_data
        )
 
        return mix
 
 
class UpdateMixSerializer(serializers.ModelSerializer):
    """Serializer for updating mix details"""
 
    class Meta:
        model = Mix
        fields = ['mix_name', 'service_type', 'charged_amount']
 
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
 































from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from .models import (
    RetailerProfile, DeliveryArea, 
    MissingProduct, CustomerDeliveryAddress
)
from mixapp.models import ShopProduct


class DeliveryAreaSerializer(serializers.ModelSerializer):
    """Serializer for delivery areas"""
    delivery_charge = serializers.SerializerMethodField()
    
    class Meta:
        model = DeliveryArea
        fields = [
            'id', 'area_name', 'postal_code',
            'custom_delivery_charge', 'delivery_charge',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_delivery_charge(self, obj):
        """Returns actual delivery charge (custom or default)"""
        return str(obj.get_delivery_charge())


class RetailerProfileSetupSerializer(serializers.ModelSerializer):
    """
    Serializer for retailer profile setup during signup.
    Called after OTP verification.
    """
    delivery_areas = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=True,
        help_text="List of area names (e.g., ['Gulshan', 'Banani'])"
    )
    
    class Meta:
        model = RetailerProfile
        fields = [
            'business_name', 'delivery_charge',
            'free_delivery_threshold', 'delivery_areas'
        ]
    
    def validate_delivery_areas(self, value):
        """Ensure at least one delivery area"""
        if not value:
            raise serializers.ValidationError(
                "At least one delivery area is required"
            )
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """Create retailer profile with delivery areas"""
        delivery_areas_data = validated_data.pop('delivery_areas')
        user = self.context['request'].user
        
        # Create retailer profile
        retailer_profile = RetailerProfile.objects.create(
            user=user,
            **validated_data
        )
        
        # Create delivery areas
        for area_name in delivery_areas_data:
            DeliveryArea.objects.create(
                retailer=retailer_profile,
                area_name=area_name.strip()
            )
        
        return retailer_profile


class RetailerDashboardStatsSerializer(serializers.Serializer):
    """Serializer for retailer dashboard statistics"""
    total_orders = serializers.IntegerField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_pending = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_cancelled = serializers.IntegerField()
    total_products = serializers.IntegerField()
    out_of_stock_count = serializers.IntegerField()


class RetailerProductSerializer(serializers.ModelSerializer):
    """
    Serializer for products managed by retailer.
    Includes retailer-specific fields.
    """
    retailer_name = serializers.CharField(source='retailer.business_name', read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ShopProduct
        fields = [
            'id', 'name', 'description', 'image_url',
            'market_price', 'quantity', 'stock_status',
            'retailer_name', 'average_rating', 'total_reviews',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'retailer_name', 'average_rating',
            'total_reviews', 'created_at', 'updated_at'
        ]
    
    def get_image_url(self, obj):
        """Get absolute URL for product image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class CreateRetailerProductSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new product by retailer.
    Auto-assigns retailer from request.user.
    """
    class Meta:
        model = ShopProduct
        fields = [
            'name', 'description', 'image',
            'market_price', 'quantity', 'barcode'
        ]
    
    def validate_name(self, value):
        """Ensure product name is unique for this retailer"""
        user = self.context['request'].user
        retailer = user.retailer_profile
        
        if ShopProduct.objects.filter(
            retailer=retailer,
            name__iexact=value.strip()
        ).exists():
            raise serializers.ValidationError(
                "You already have a product with this name"
            )
        
        return value.strip()
    
    @transaction.atomic
    def create(self, validated_data):
        """Create product and link to retailer"""
        user = self.context['request'].user
        retailer = user.retailer_profile
        
        # Create product with retailer link
        product = ShopProduct.objects.create(
            retailer=retailer,
            **validated_data
        )
        
        return product


class MissingProductSerializer(serializers.ModelSerializer):
    """Serializer for missing product requests"""
    class Meta:
        model = MissingProduct
        fields = [
            'id', 'product_name', 'category', 'brand',
            'additional_notes', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']


class CustomerDeliveryAddressSerializer(serializers.ModelSerializer):
    """Serializer for customer delivery addresses"""
    class Meta:
        model = CustomerDeliveryAddress
        fields = [
            'id', 'address_label', 'full_address', 'area',
            'postal_code', 'phone_number', 'is_default',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    @transaction.atomic
    def create(self, validated_data):
        """Create address and handle is_default flag"""
        user = self.context['request'].user
        is_default = validated_data.get('is_default', False)
        
        # If this is default, unset others
        if is_default:
            CustomerDeliveryAddress.objects.filter(
                user=user,
                is_default=True
            ).update(is_default=False)
        
        # Create new address
        address = CustomerDeliveryAddress.objects.create(
            user=user,
            **validated_data
        )
        
        return address
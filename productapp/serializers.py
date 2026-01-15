
# mixapp/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import ShopProduct, UserProduct, ProductReview
from clientapp.models import Client


class ShoppingCartSerializer(serializers.ModelSerializer):
    shop_product = ShopProductDetailSerializer(read_only=True)
    shop_product_id = serializers.UUIDField(write_only=True)
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
    product_id = serializers.UUIDField(required=False)
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

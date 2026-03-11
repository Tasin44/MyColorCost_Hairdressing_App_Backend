from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
# from django.contrib.auth.models import User
from django.conf import settings
from .models import (
    RetailerProfile, DeliveryArea, 
    MissingProduct, CustomerDeliveryAddress
)
from mixapp.models import ShopProduct
from django.contrib.auth import get_user_model
import json
from django.core.validators import MinValueValidator
User = get_user_model()

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
            'business_name', 'business_logo',# ✅ ADDed 28th feb
            'delivery_charge',
            'free_delivery_threshold', 'delivery_areas','api_key'
        ]
        extra_kwargs = {
            'api_key': {'required': False, 'allow_blank': True, 'allow_null': True} , 'business_logo': {'required': False}   # ✅ ADDed 28th feb
        }
    
    def validate_delivery_areas(self, value):
        """Ensure at least one delivery area"""
        if not value:
            raise serializers.ValidationError(
                "At least one delivery area is required"
            )
        return value
    # ✅ ADD THIS METHOD
    def validate_api_key(self, value):
        """Convert empty string to None to avoid unique constraint issues"""
        if not value or value.strip() == "":
            return None
        return value.strip()
    @transaction.atomic
    def create(self, validated_data):
        """Create retailer profile with delivery areas"""
        delivery_areas_data = validated_data.pop('delivery_areas')
        user = self.context['request'].user

        # ✅ Set is_approved=True during creation
        validated_data['is_approved'] = True

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


# ✅ ADDed 28th feb==================================================================================\
# ✅ ADD THIS — place right after RetailerProfileSetupSerializer

class RetailerProfileUpdateSerializer(serializers.ModelSerializer):
    """For PATCH update of retailer profile"""
    class Meta:
        model = RetailerProfile
        fields = [
            'business_name', 'business_logo',
            'delivery_charge', 'free_delivery_threshold'
        ]
        extra_kwargs = {
            'business_name': {'required': False},
            'business_logo': {'required': False},
            'delivery_charge': {'required': False},
            'free_delivery_threshold': {'required': False},
        }

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RetailerPublicSerializer(serializers.ModelSerializer):
    """For public retailer list (app store - all retailers)"""
    business_logo_url = serializers.SerializerMethodField()
    retailer_email = serializers.CharField(source='user.email', read_only=True)
    retailer_contact = serializers.CharField(source='user.phone_number', read_only=True)  # adjust field name if different
    delivery_areas = serializers.SerializerMethodField()

    class Meta:
        model = RetailerProfile
        fields = [
            'id', 'business_name', 'business_logo_url',
            'retailer_email', 'retailer_contact',
            'delivery_charge', 'free_delivery_threshold',
            'delivery_areas'
        ]

    def get_business_logo_url(self, obj):
        request = self.context.get('request')
        if obj.business_logo and request:
            return request.build_absolute_uri(obj.business_logo.url)
        return None

    def get_delivery_areas(self, obj):
        return list(
            obj.delivery_areas.filter(is_active=True).values_list('area_name', flat=True)
        )


#=====================================================================================================/

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
    image_url = serializers.SerializerMethodField()#image_url is a SerializerMethodField, not a model field. DRF only uses SerializerMethodField for reading, never for writing.
    def validate_market_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Market price cannot be negative.")
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value

    def validate_vat(self, value):
        if value < 0:
            raise serializers.ValidationError("VAT cannot be negative.")
        return value
    class Meta:
        model = ShopProduct
        fields = [
            'id', 'name', 'description', 'image_url',
            'market_price','discounted_market_price','quantity', 'stock_status','vat',# ✅ ADDed 28th feb
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
class UpdateRetailerProductSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False)

    class Meta:
        model = ShopProduct
        fields = ['name', 'description', 'image', 'market_price', 'quantity', 'barcode', 'vat']
    '''
     def get_image_url(self, obj):
        """Get absolute URL for product image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None   

    Reason:
    Your UpdateRetailerProductSerializer is only meant for updating fields. 
    You added get_image_url in it, but it is ignored because:
    get_image_url is a SerializerMethodField pattern, but you didn’t declare image_url = serializers.SerializerMethodField() in this serializer.
    Without that, DRF never calls get_image_url.
    So even though you define get_image_url, it does nothing in the update serializer.
    
    '''

class CreateRetailerProductSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new product by retailer.
    Auto-assigns retailer from request.user.
    """
    market_price = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    quantity = serializers.IntegerField(
        validators=[MinValueValidator(0)]
    )
    vat = serializers.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    class Meta:
        model = ShopProduct
        fields = [
            'name', 'description', 'image',
            'market_price', 'quantity', 'barcode','vat'# ✅ ADDed 28th feb
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


#============================================================================================================\

# serializers.py

class RetailerProfilePublicSetupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    delivery_areas = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=True
    )

    class Meta:
        model = RetailerProfile
        fields = [
            'email',
            'business_name',
             'business_logo',# ✅ ADDed 28th feb
            'delivery_charge',
            'free_delivery_threshold',
            'delivery_areas',
            'api_key'
        ]
        extra_kwargs = {
            'api_key': {'required': False, 'allow_blank': True, 'allow_null': True},
            'business_logo': {'required': False}, # ✅ ADDed 28th feb
        }

    def validate_email(self, value):
        email = value.lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        if user.role != 'retailer':
            raise serializers.ValidationError("This user is not a retailer.")

        if not user.verified:
            raise serializers.ValidationError("Email is not verified.")

        if hasattr(user, 'retailer_profile'):
            raise serializers.ValidationError("Retailer profile already exists.")

        self.context['user'] = user
        return email

    def validate_delivery_areas(self, value):
        if not value:
            raise serializers.ValidationError("At least one delivery area is required.")
        # ✅ FIX: If sent as JSON string from form-data, parse it
        if len(value) == 1:
            try:
                parsed = json.loads(value[0])
                if isinstance(parsed, list):
                    return [v.strip() for v in parsed]
            except (json.JSONDecodeError, TypeError):
                pass
        
        return [v.strip() for v in value]
        # return value

    def validate_api_key(self, value):
        if not value or value.strip() == "":
            return None
        return value.strip()

    @transaction.atomic
    def create(self, validated_data):
        delivery_areas_data = validated_data.pop('delivery_areas')
        validated_data.pop('email')

        user = self.context['user']

        validated_data['is_approved'] = True

        retailer_profile = RetailerProfile.objects.create(
            user=user,
            **validated_data
        )

        for area_name in delivery_areas_data:
            DeliveryArea.objects.create(
                retailer=retailer_profile,
                area_name=area_name.strip()
            )

        return retailer_profile


#=======================================================================================


# ...existing code...

class BulkDiscountSerializer(serializers.Serializer):
    """Serializer for bulk discount on all retailer products"""
    
    DISCOUNT_TYPE_CHOICES = ['percentage', 'amount']
    
    discount_type = serializers.ChoiceField(
        choices=DISCOUNT_TYPE_CHOICES,
        help_text="'percentage' or 'amount'"
    )
    discount_value = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text="2 means 2% (percentage) or $2 (amount)"
    )

    def validate(self, data):
        if data['discount_type'] == 'percentage':
            if data['discount_value'] >= 100:
                raise serializers.ValidationError(
                    "Percentage discount must be less than 100%"
                )
        return data







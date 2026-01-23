# clientapp/serializers.py
from rest_framework import serializers
from django.db import transaction
from .models import Client, ClientImage


class ClientImageSerializer(serializers.ModelSerializer):
    """Serializer for client images (before/after photos)"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientImage
        fields = ['id', 'image_type', 'image_url', 'upload_date']
        read_only_fields = ['id', 'upload_date']
    
    def get_image_url(self, obj):
        """Get absolute URL for image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ClientImageUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading client images"""
    image_url = serializers.SerializerMethodField()
    class Meta:
        model = ClientImage
        fields = ['image_type', 'image' ,'image_url']
    
    def validate_image_type(self, value):
        """Validate image type"""
        if value not in ['before', 'after']:
            raise serializers.ValidationError("Image type must be 'before' or 'after'")
        return value
    def get_image_url(self, obj):
        """Get absolute URL for image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

class ClientListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for client list view.
    Only includes essential fields for performance.
    """
    created_by = serializers.SerializerMethodField()
    has_images = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'contact_number', 'email',
            'service_type', 'total_mixes', 'last_visit_date',
            'next_appointment_date', 'created_by', 'has_images',
            'created_at'
        ]
    
    def get_created_by(self, obj):
        """Return who created the client"""
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
    
    def get_has_images(self, obj):
        """Check if client has any images (optimized)"""
        # Use prefetch_related in view to avoid N+1
        # return obj.images.exists() if hasattr(obj, 'images') else False
        return obj.images.exists()#hasattr(obj, 'images') check is unnecessary,images always exists due to related_name


class ClientDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single client view.
    Includes related data like images and mix history.
    """
    images = ClientImageSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField()
    mix_history = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'name', 'contact_number', 'email',
            'service_type', 'skin_test_date', 'notes',
            'total_mixes', 'last_visit_date', 'next_appointment_date',
            'images', 'created_by', 'mix_history',
            'created_at', 'updated_at'
        ]
    
    def get_created_by(self, obj):
        """Return who created the client"""
        if obj.sub_user:
            return {
                'type': 'staff',
                'name': obj.sub_user.name,
                'id': obj.sub_user.id,
                'email': obj.sub_user.email
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email,
            'id': obj.user.id,
            'email': obj.user.email
        }
    
    def get_mix_history(self, obj):
        """
        Get recent mix history for the client.
        Optimized to avoid N+1 queries.
        """
        # Import here to avoid circular imports
        from mixapp.serializers import MixListSerializer
        
        # Get latest 10 mixes
        recent_mixes = obj.mixes.select_related('user', 'sub_user').prefetch_related(
            'mix_products'
        ).order_by('-created_date', '-created_time')[:10]
        
        return MixListSerializer(recent_mixes, many=True, context=self.context).data


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating clients.
    """
    
    class Meta:
        model = Client
        fields = [
            'name', 'contact_number', 'email',
            'service_type', 'skin_test_date', 'notes',
            'next_appointment_date'
        ]
    
    def validate_name(self, value):
        """Validate client name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Client name is required")
        return value.strip()
    
    def validate_email(self, value):
        """Validate email format if provided"""
        if value:
            value = value.lower().strip()
        return value
    
    def validate_contact_number(self, value):
        """Validate contact number if provided"""
        # if value:
        #     # Remove spaces and check if it's numeric
        #     clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
        #     if not clean_number.isdigit():
        #         raise serializers.ValidationError("Invalid contact number format")
        # return value
        if value is None:
            return value
        
        user = self.context['request'].user
        
        # Check if contact number already exists for this user
        # contact_number = user.get('contact_number')
        # if contact_number:
        existing = Client.objects.filter(
                user=user,
                contact_number=value
        )
        if self.instance:
                existing = existing.exclude(id=self.instance.id)
            
        if existing.exists():
                raise serializers.ValidationError({
                    'contact_number': 'A client with this contact number already exists.'
                })
        
        return value
        
        
    @transaction.atomic
    def create(self, validated_data):
        """
        Create client and associate with user/sub_user.
        The view will set user and sub_user fields.
        """
        return super().create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update client information"""
        return super().update(instance, validated_data)


class ClientStatsSerializer(serializers.Serializer):
    """
    Serializer for client statistics dashboard.
    Used for aggregated data display.
    """
    total_clients = serializers.IntegerField()
    clients_this_month = serializers.IntegerField()
    clients_with_appointments = serializers.IntegerField()
    total_mixes_all_clients = serializers.IntegerField()
    active_clients = serializers.IntegerField()  # Clients with visits in last 3 months
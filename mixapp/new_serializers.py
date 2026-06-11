# mixapp/new_serializers.py
#
# NEW serializers only — existing mixapp/serializers.py is untouched.
#

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .models import Mix, MixProduct, Bowl, BowlProduct, UserProduct
from clientapp.models import Client
from authapp.models import SubUser


# ===========================================================================
# Bowl / BowlProduct helpers
# ===========================================================================

class BowlProductInputSerializer(serializers.Serializer):
    """Input: a single product entry within a bowl."""
    user_product_id = serializers.IntegerField()
    used_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01')
    )
    user_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    market_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )

    def validate_user_product_id(self, value):
        """Validated later in the parent serializer where we have the owner context."""
        return value


class BowlInputSerializer(serializers.Serializer):
    """Input: one bowl with its own products list."""
    service_name = serializers.CharField(max_length=255)
    mix_name = serializers.CharField(max_length=255)
    charged_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        min_value=Decimal('0.00')
    )
    bleach_timer_start_time = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    products = BowlProductInputSerializer(many=True, required=False, default=list)


class BowlProductOutputSerializer(serializers.ModelSerializer):
    """Read serializer for a single BowlProduct."""
    class Meta:
        model = BowlProduct
        fields = [
            'id', 'product_name', 'used_weight',
            'market_price', 'user_price', 'each_item_cost',
        ]


class BowlOutputSerializer(serializers.ModelSerializer):
    """Read serializer for a Bowl with its products."""
    products = BowlProductOutputSerializer(source='bowl_products', many=True, read_only=True)

    class Meta:
        model = Bowl
        fields = [
            'id', 'service_name', 'mix_name',
            'charged_amount', 'bleach_timer_start_time',
            'total_cost', 'products', 'created_at',
        ]


# ===========================================================================
# Main: New Mix Creation
# ===========================================================================

class NewMixCreateSerializer(serializers.Serializer):
    """
    POST /mix/mixes/new/

    Body:
    {
        "client_id": 5,              ← mandatory
        "service_type": "2",         ← service type ID (string or int) from ServiceType list
        "bowls": [
            {
                "service_name": "Hair Color",
                "mix_name": "Spa mix14",
                "charged_amount": 400,
                "bleach_timer_start_time": "2024-01-23T10:30:00",
                "products": [
                    {
                        "user_product_id": 26,
                        "used_weight": 5,
                        "user_price": 200,
                        "market_price": 200
                    }
                ]
            }
        ]
    }
    """
    client_id = serializers.IntegerField(
        help_text="Mandatory — mix won't be created without a valid client"
    )
    service_type = serializers.CharField(
        max_length=100,
        help_text="Service type ID (from your service list) or service name string"
    )
    bowls = BowlInputSerializer(many=True, required=False, default=list)

    def _get_owner(self, user):
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            return user.staff_profile.main_user, user.staff_profile
        return user, None

    def validate_client_id(self, value):
        user = self.context['request'].user
        owner, _ = self._get_owner(user)
        if not Client.objects.filter(id=value, user=owner).exists():
            raise serializers.ValidationError(
                "Client not found. A valid client is required to create a mix."
            )
        return value

    def validate_service_type(self, value):
        """Accept either a numeric ID string or a plain service name."""
        return value.strip()

    def validate(self, data):
        user = self.context['request'].user
        owner, _ = self._get_owner(user)

        # Validate all products in every bowl
        for bowl_index, bowl_data in enumerate(data.get('bowls', [])):
            for prod_index, prod_data in enumerate(bowl_data.get('products', [])):
                uid = prod_data['user_product_id']
                used_weight = prod_data['used_weight']

                try:
                    up = UserProduct.objects.get(id=uid, user=owner)
                except UserProduct.DoesNotExist:
                    raise serializers.ValidationError({
                        'bowls': f"Bowl {bowl_index + 1}, product {prod_index + 1}: "
                                 f"UserProduct id={uid} not found."
                    })

                if not up.is_available:
                    raise serializers.ValidationError({
                        'bowls': f"Bowl {bowl_index + 1}: '{up.product.name}' is not available."
                    })

                if up.current_weight_grams < used_weight:
                    raise serializers.ValidationError({
                        'bowls': f"Bowl {bowl_index + 1}: insufficient weight for "
                                 f"'{up.product.name}'. Available: {up.current_weight_grams}g."
                    })

        return data

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        owner, sub_user = self._get_owner(user)

        client = Client.objects.get(id=validated_data['client_id'])
        service_type_raw = validated_data['service_type']
        bowls_data = validated_data.get('bowls', [])

        # Resolve service_type FK (try numeric ID first, then name)
        from appointmentapp.models import ServiceType as ServiceTypeModel
        service_type_fk = None
        service_type_name = service_type_raw
        try:
            service_type_id = int(service_type_raw)
            st = ServiceTypeModel.objects.filter(id=service_type_id, user=owner).first()
            if st:
                service_type_fk = st
                service_type_name = st.name
        except (ValueError, TypeError):
            # It's a name string — try to find it
            st = ServiceTypeModel.objects.filter(name__iexact=service_type_raw, user=owner).first()
            if st:
                service_type_fk = st

        # Create the parent Mix (uses existing Mix model)
        mix = Mix.objects.create(
            user=owner,
            sub_user=sub_user,
            client=client,
            mix_name=bowls_data[0]['mix_name'] if bowls_data else 'Mix',
            service_type=service_type_name,   # existing CharField (kept for backward compat)
            service_type_fk=service_type_fk,  # new FK field
        )

        # Create Bowls and their products
        for bowl_data in bowls_data:
            bowl = Bowl.objects.create(
                mix=mix,
                service_name=bowl_data['service_name'],
                mix_name=bowl_data['mix_name'],
                charged_amount=bowl_data.get('charged_amount'),
                bleach_timer_start_time=bowl_data.get('bleach_timer_start_time'),
            )

            for prod_data in bowl_data.get('products', []):
                up = UserProduct.objects.get(id=prod_data['user_product_id'], user=owner)

                market_price = prod_data.get('market_price') or up.product.market_price
                raw_user_price = prod_data.get('user_price') or up.user_price
                original_weight = up.original_weight_grams
                used_weight = prod_data['used_weight']

                if original_weight and original_weight > 0:
                    price_per_gram = Decimal(str(raw_user_price)) / original_weight
                    each_item_cost = (price_per_gram * used_weight).quantize(Decimal('0.01'))
                else:
                    each_item_cost = Decimal('0.00')

                BowlProduct.objects.create(
                    bowl=bowl,
                    user_product=up,
                    product_name=up.product.name,
                    used_weight=used_weight,
                    market_price=market_price,
                    user_price=raw_user_price,
                    each_item_cost=each_item_cost,
                )

                # Reduce product weight
                up.reduce_weight(used_weight)

            # Update bowl total cost
            bowl.calculate_total_cost()

        # Update mix total cost from all bowls
        from django.db.models import Sum
        bowl_totals = Bowl.objects.filter(mix=mix).aggregate(
            t_cost=Sum('total_cost'),
            t_charged=Sum('charged_amount')
        )
        total_bowls_cost = bowl_totals['t_cost'] or Decimal('0.00')
        total_charged_amount = bowl_totals['t_charged'] or Decimal('0.00')
        
        # Add service fee if available
        service_fee = Decimal('0.00')
        if mix.service_type_fk and mix.service_type_fk.service_fee:
            service_fee = mix.service_type_fk.service_fee
            
        mix.total_cost = total_bowls_cost + service_fee
        mix.charged_amount = total_charged_amount
        
        if mix.charged_amount is not None:
            mix.profit = mix.charged_amount - mix.total_cost
        else:
            mix.profit = Decimal('0.00')
            
        mix.save(update_fields=['charged_amount', 'total_cost', 'profit', 'updated_at'])

        # Update client stats
        if client:
            client.update_stats()

        return mix


# ===========================================================================
# Read Serializers for new Mix (with bowls)
# ===========================================================================

class NewMixListSerializer(serializers.ModelSerializer):
    """List view for the new mix format, includes bowl count and created_by."""
    client_name = serializers.CharField(source='client.name', read_only=True, default=None)
    client_id = serializers.IntegerField(source='client.id', read_only=True, allow_null=True)
    created_by = serializers.SerializerMethodField()
    bowl_count = serializers.SerializerMethodField()
    service_type_info = serializers.SerializerMethodField()

    class Meta:
        model = Mix
        fields = [
            'id', 'client_name', 'client_id',
            'service_type', 'service_type_info',
            'total_cost', 'charged_amount', 'profit',
            'created_date', 'created_time',
            'bowl_count', 'created_by',
        ]

    def get_bowl_count(self, obj):
        return obj.bowls.count()

    def get_service_type_info(self, obj):
        if obj.service_type_fk:
            return {
                'id': obj.service_type_fk.id,
                'name': obj.service_type_fk.name,
            }
        return {'id': None, 'name': obj.service_type}

    def get_created_by(self, obj):
        if obj.sub_user:
            return {
                'type': 'staff',
                'name': obj.sub_user.name,
                'id': str(obj.sub_user.user.id),
                'email': obj.sub_user.email,
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email,
            'id': str(obj.user.id),
            'email': obj.user.email,
        }


class NewMixDetailSerializer(serializers.ModelSerializer):
    """Detailed view for a single Mix with all bowls and products."""
    client_name = serializers.CharField(source='client.name', read_only=True, default=None)
    client_id = serializers.IntegerField(source='client.id', read_only=True, allow_null=True)
    created_by = serializers.SerializerMethodField()
    bowls = BowlOutputSerializer(many=True, read_only=True)
    service_type_info = serializers.SerializerMethodField()

    class Meta:
        model = Mix
        fields = [
            'id', 'client_name', 'client_id',
            'service_type', 'service_type_info',
            'charged_amount', 'total_cost', 'profit',
            'created_date', 'created_time', 'created_at',
            'bowls', 'created_by',
        ]

    def get_service_type_info(self, obj):
        if obj.service_type_fk:
            return {
                'id': obj.service_type_fk.id,
                'name': obj.service_type_fk.name,
            }
        return {'id': None, 'name': obj.service_type}

    def get_created_by(self, obj):
        if obj.sub_user:
            return {
                'type': 'staff',
                'name': obj.sub_user.name,
                'id': str(obj.sub_user.user.id),
                'email': obj.sub_user.email,
            }
        return {
            'type': 'owner',
            'name': obj.user.name or obj.user.email,
            'id': str(obj.user.id),
            'email': obj.user.email,
        }

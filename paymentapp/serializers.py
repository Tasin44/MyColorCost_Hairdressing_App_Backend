#=========================================================


from rest_framework import serializers
from .models import Payment, PaymentRetailerSplit, RetailerOrder

class RetailerOrderSerializer(serializers.ModelSerializer):
    """Serializer for retailer orders"""
    customer_name = serializers.CharField(source='payment.user.name', read_only=True)
    customer_email = serializers.CharField(source='payment.user.email', read_only=True)
    
    class Meta:
        model = RetailerOrder
        fields = [
            'id', 'product_name', 'quantity', 'unit_price', 'total_amount',
            'delivery_full_address', 'delivery_area', 'delivery_postal_code',
            'delivery_phone', 'status', 'created_at', 'updated_at',
            'customer_name', 'customer_email'
        ]
        read_only_fields = [
            'id', 'product_name', 'quantity', 'unit_price', 'total_amount',
            'delivery_full_address', 'delivery_area', 'delivery_postal_code',
            'delivery_phone', 'created_at', 'updated_at'
        ]


class RetailerPaymentSummarySerializer(serializers.ModelSerializer):
    """Serializer for retailer payment summary"""
    customer_name = serializers.CharField(source='payment.user.name', read_only=True)
    customer_email = serializers.CharField(source='payment.user.email', read_only=True)
    payment_date = serializers.DateTimeField(source='payment.created_at', read_only=True)
    
    class Meta:
        model = PaymentRetailerSplit
        fields = [
            'id', 'customer_name', 'customer_email', 'payment_date',
            'total_transfer_amount', 'transfer_status', 'transfer_id'
        ]


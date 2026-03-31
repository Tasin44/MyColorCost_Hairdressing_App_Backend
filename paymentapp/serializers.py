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

#==============================================================================================================
#Retailer sales graph api 
# paymentapp/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import PaymentRetailerSplit

class MonthlySalesSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month_index = serializers.IntegerField()  # Jan=0, Feb=1 ... Dec=11
    month_name = serializers.CharField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    order_count = serializers.IntegerField()


class SalesChartSerializer(serializers.Serializer):
    labels = serializers.ListField(child=serializers.CharField())
    sales = serializers.ListField(child=serializers.DecimalField(max_digits=12, decimal_places=2))
    orders = serializers.ListField(child=serializers.IntegerField())


class UserOrderSerializer(serializers.ModelSerializer):
    retailer_name = serializers.CharField(source='retailer.business_name', read_only=True)

    class Meta:
        model = RetailerOrder
        fields = [
            'id',
            'product_name',
            'quantity',
            'unit_price',
            'total_amount',
            'retailer_name',
            'status',
            'created_at'
        ]










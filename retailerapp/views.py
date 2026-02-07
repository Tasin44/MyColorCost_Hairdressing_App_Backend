from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal

from .models import (
    RetailerProfile, DeliveryArea,
    MissingProduct, CustomerDeliveryAddress
)
from mixapp.models import ShopProduct
from .serializers import (
    RetailerProfileSetupSerializer, DeliveryAreaSerializer,
    RetailerDashboardStatsSerializer, RetailerProductSerializer,
    CreateRetailerProductSerializer, MissingProductSerializer,
    CustomerDeliveryAddressSerializer
)
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StandardResponseMixin:
    """Mixin for consistent API responses"""
    
    def success_response(self, data=None, message="Success", status_code=200):
        response = {
            "success": True,
            "statusCode": status_code,
            "message": message,
        }
        if data is not None:
            response["data"] = data
        return Response(response, status=status_code)
    
    def error_response(self, message, status_code=400, data=None):
        response = {
            "success": False,
            "statusCode": status_code,
            "message": message,
        }
        if data is not None:
            response["data"] = data
        return Response(response, status=status_code)


class RetailerProfileSetupView(StandardResponseMixin, APIView):
    """
    Setup retailer profile after signup.
    Must be called after OTP verification.
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Create retailer profile with delivery config"""
        user = request.user
        
        # ✅ Check if user is retailer
        if user.role != 'retailer':
            return self.error_response(
                "Only retailer accounts can access this endpoint",
                status_code=403
            )
        
        # ✅ Check if profile already exists
        if hasattr(user, 'retailer_profile'):
            return self.error_response(
                "Retailer profile already exists",
                status_code=400
            )
        
        serializer = RetailerProfileSetupSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            retailer_profile = serializer.save()
            
            return self.success_response(
                data={
                    'business_name': retailer_profile.business_name,
                    'delivery_charge': str(retailer_profile.delivery_charge),
                    'free_delivery_threshold': str(retailer_profile.free_delivery_threshold),
                    'delivery_areas': list(
                        retailer_profile.delivery_areas.values('id', 'area_name')
                    )
                },
                message="Retailer profile setup completed",
                status_code=201
            )
        
        return self.error_response(
            "Profile setup failed",
            status_code=400,
            data=serializer.errors
        )


class RetailerDashboardView(StandardResponseMixin, APIView):
    """
    Retailer dashboard home statistics.
    Shows: total orders, sales, pending, cancelled.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get retailer dashboard stats"""
        user = request.user
        
        # ✅ Verify retailer
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response(
                "Unauthorized access",
                status_code=403
            )
        
        retailer = user.retailer_profile
        
        # ✅ Get product statistics (DB-efficient single query)
        product_stats = ShopProduct.objects.filter(
            retailer=retailer
        ).aggregate(
            total_products=Count('id'),
            out_of_stock_count=Count('id', filter=Q(stock_status='out_of_stock'))
        )
        
        # ✅ Prepare stats
        stats = {
            'total_orders': retailer.total_orders,
            'total_sales': retailer.total_sales,
            'total_pending': retailer.total_pending,
            'total_cancelled': retailer.total_cancelled,
            'total_products': product_stats['total_products'],
            'out_of_stock_count': product_stats['out_of_stock_count']
        }
        
        serializer = RetailerDashboardStatsSerializer(data=stats)
        serializer.is_valid()
        
        return self.success_response(
            data=serializer.data,
            message="Dashboard stats retrieved",
            status_code=200
        )


class RetailerProductListView(StandardResponseMixin, APIView):
    """
    List all products for retailer.
    Supports filtering by stock status.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get retailer's products"""
        user = request.user
        
        # ✅ Verify retailer
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response(
                "Unauthorized access",
                status_code=403
            )
        
        retailer = user.retailer_profile
        
        # ✅ Get products (optimized query)
        queryset = ShopProduct.objects.filter(
            retailer=retailer
        ).select_related('retailer').order_by('-created_at')
        
        # ✅ Filter by stock status (optional)
        stock_status = request.query_params.get('stock_status')
        if stock_status in ['in_stock', 'out_of_stock', 'low_stock']:
            queryset = queryset.filter(stock_status=stock_status)
        
        # ✅ Search by name (optional)
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        serializer = RetailerProductSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        
        return self.success_response(
            data={
                'products': serializer.data,
                'total_count': queryset.count()
            },
            message="Products retrieved",
            status_code=200
        )


class RetailerProductCreateView(StandardResponseMixin, APIView):
    """
    Create new product (retailer only).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # For image upload
    
    @transaction.atomic
    def post(self, request):
        """Create new product"""
        user = request.user
        
        # ✅ Verify retailer
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response(
                "Unauthorized access",
                status_code=403
            )
        
        serializer = CreateRetailerProductSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            product = serializer.save()
            
            response_serializer = RetailerProductSerializer(
                product,
                context={'request': request}
            )
            
            return self.success_response(
                data=response_serializer.data,
                message="Product created successfully",
                status_code=201
            )
        
        return self.error_response(
            "Failed to create product",
            status_code=400,
            data=serializer.errors
        )


class RetailerProductDetailView(StandardResponseMixin, APIView):
    """
    Get, update, or delete a specific product (retailer only).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_object(self, request, product_id):
        """Get product if it belongs to retailer"""
        user = request.user
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return None
        
        try:
            return ShopProduct.objects.get(
                id=product_id,
                retailer=user.retailer_profile
            )
        except ShopProduct.DoesNotExist:
            return None
    
    def get(self, request, product_id):
        """Get product details"""
        product = self.get_object(request, product_id)
        
        if not product:
            return self.error_response(
                "Product not found",
                status_code=404
            )
        
        serializer = RetailerProductSerializer(
            product,
            context={'request': request}
        )
        
        return self.success_response(
            data=serializer.data,
            message="Product retrieved",
            status_code=200
        )
    
    @transaction.atomic
    def patch(self, request, product_id):
        """Update product (excluding retailer_name and rating)"""
        product = self.get_object(request, product_id)
        
        if not product:
            return self.error_response(
                "Product not found",
                status_code=404
            )
        
        # ✅ Allowed fields for update
        allowed_fields = [
            'name', 'description', 'image', 'market_price',
            'quantity', 'barcode'
        ]
        
        update_data = {
            k: v for k, v in request.data.items() if k in allowed_fields
        }
        
        serializer = RetailerProductSerializer(
            product,
            data=update_data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            product = serializer.save()
            
            return self.success_response(
                data=serializer.data,
                message="Product updated successfully",
                status_code=200
            )
        
        return self.error_response(
            "Failed to update product",
            status_code=400,
            data=serializer.errors
        )
    
    @transaction.atomic
    def delete(self, request, product_id):
        """Delete product"""
        product = self.get_object(request, product_id)
        
        if not product:
            return self.error_response(
                "Product not found",
                status_code=404
            )
        
        product_name = product.name
        product.delete()
        
        return self.success_response(
            message=f"Product '{product_name}' deleted successfully",
            status_code=200
        )


class MissingProductRequestView(StandardResponseMixin, APIView):
    """
    Submit missing product request (any authenticated user).
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Create missing product request"""
        serializer = MissingProductSerializer(data=request.data)
        
        if serializer.is_valid():
            missing_product = MissingProduct.objects.create(
                requested_by=request.user,
                **serializer.validated_data
            )
            
            response_serializer = MissingProductSerializer(missing_product)
            
            return self.success_response(
                data=response_serializer.data,
                message="Product request submitted. We'll notify you when available.",
                status_code=201
            )
        
        return self.error_response(
            "Failed to submit request",
            status_code=400,
            data=serializer.errors
        )


class DeliveryAddressListCreateView(StandardResponseMixin, APIView):
    """
    List or create delivery addresses (customer side).
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all user's delivery addresses"""
        addresses = CustomerDeliveryAddress.objects.filter(
            user=request.user
        ).order_by('-is_default', '-created_at')
        
        serializer = CustomerDeliveryAddressSerializer(addresses, many=True)
        
        return self.success_response(
            data={
                'addresses': serializer.data,
                'total_count': addresses.count()
            },
            message="Delivery addresses retrieved",
            status_code=200
        )
    
    @transaction.atomic
    def post(self, request):
        """Create new delivery address"""
        serializer = CustomerDeliveryAddressSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            address = serializer.save()
            
            response_serializer = CustomerDeliveryAddressSerializer(address)
            
            return self.success_response(
                data=response_serializer.data,
                message="Delivery address added",
                status_code=201
            )
        
        return self.error_response(
            "Failed to add address",
            status_code=400,
            data=serializer.errors
        )

#=======================================================================================================================================

#Stripe code for retailer 
# Add to retailerapp/views.py



class RetailerStripeOnboardView(StandardResponseMixin, APIView):
    """Start Stripe Connect onboarding for retailer"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)
        
        retailer = user.retailer_profile
        
        if retailer.stripe_connected:
            return self.error_response("Already connected to Stripe", status_code=400)
        
        try:
            # Create Stripe Connect account if doesn't exist
            if not retailer.stripe_account_id:
                account = stripe.Account.create(
                    type='express',
                    country='GB',  # Change based on your country
                    email=user.email,
                    capabilities={
                        'transfers': {'requested': True}
                    }
                )
                retailer.stripe_account_id = account.id
                retailer.save(update_fields=['stripe_account_id'])
            
            # Create onboarding link
            account_link = stripe.AccountLink.create(
                account=retailer.stripe_account_id,
                type='account_onboarding',
                refresh_url=f"{settings.BASE_URL}/retailer/stripe/refresh",
                return_url=f"{settings.BASE_URL}/retailer/stripe/complete"
            )
            
            return self.success_response(
                data={
                    'onboarding_url': account_link.url,
                    'account_id': retailer.stripe_account_id
                },
                message="Stripe onboarding started",
                status_code=200
            )
        
        except stripe.error.StripeError as e:
            return self.error_response(str(e), status_code=500)


class RetailerStripeCompleteView(StandardResponseMixin, APIView):
    """Handle Stripe onboarding completion"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        retailer = user.retailer_profile
        
        try:
            account = stripe.Account.retrieve(retailer.stripe_account_id)
            
            if account.charges_enabled and account.details_submitted:
                retailer.stripe_connected = True
                retailer.stripe_connection_date = timezone.now()
                retailer.save()
                
                return self.success_response(
                    message="Stripe account connected successfully",
                    status_code=200
                )
            else:
                return self.error_response(
                    "Stripe onboarding incomplete",
                    status_code=400
                )
        
        except stripe.error.StripeError as e:
            return self.error_response(str(e), status_code=500)








































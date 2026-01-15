from django.shortcuts import render

# Create your views here.
# mixapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
 
from .models import ShopProduct, UserProduct, Mix, MixProduct, ProductReview
from clientapp.models import Client
from .serializers import (
    ShopProductListSerializer, ShopProductDetailSerializer,
    UserProductSerializer, CreateUserProductSerializer,
    MixListSerializer, MixDetailSerializer, CreateMixSerializer,
    UpdateMixSerializer, AddProductToMixSerializer,
    MixProductSerializer, ProductReviewSerializer,
    CreateProductReviewSerializer, MixStatsSerializer
)
 
 
class StandardResponseMixin:
    """Mixin for consistent API responses"""
 
    def success_response(self, data=None, message="Success", status_code=200):
        return Response({
            "success": True,
            "statusCode": status_code,
            "message": message,
            "data": data
        }, status=status_code)
 
    def error_response(self, message, status_code=400, data=None):
        return Response({
            "success": False,
            "statusCode": status_code,
            "message": message,
            "data": data
        }, status=status_code)
 
 
#$===============================================productapp-views.py===========================================================
# ============================================
# SHOP PRODUCTS (Master Catalog)
# ============================================
 
class ShopProductListView(StandardResponseMixin, APIView):
    """
    List all shop products with search and filtering.
    These are products that can be scanned and added to inventory.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """
        Get product list with optional filtering.
 
        Query params:
        - search: Search by name or retailer
        - min_rating: Filter by minimum rating
        - retailer: Filter by retailer name
        """
        queryset = ShopProduct.objects.all()
 
        # Search
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(retailer_name__icontains=search)
            )
 
        # Filter by rating
        min_rating = request.query_params.get('min_rating')
        if min_rating:
            try:
                queryset = queryset.filter(average_rating__gte=float(min_rating))
            except ValueError:
                pass
 
        # Filter by retailer
        retailer = request.query_params.get('retailer', '').strip()
        if retailer:
            queryset = queryset.filter(retailer_name__iexact=retailer)
 
        # Order by rating and name
        queryset = queryset.order_by('-average_rating', 'name')
 
        serializer = ShopProductListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
 
        return self.success_response(
            data={
                'products': serializer.data,
                'total_count': queryset.count()
            },
            message="Products retrieved successfully",
            status_code=200
        )
 
 
class ShopProductDetailView(StandardResponseMixin, APIView):
    """Get detailed information about a specific product"""
    permission_classes = [IsAuthenticated]
 
    def get(self, request, product_id):
        """Get product details including reviews"""
        try:
            product = ShopProduct.objects.prefetch_related('reviews').get(
                id=product_id
            )
        except ShopProduct.DoesNotExist:
            return self.error_response(
                "Product not found",
                status_code=404
            )
 
        # Get product details
        serializer = ShopProductDetailSerializer(
            product,
            context={'request': request}
        )
 
        # Get recent reviews
        recent_reviews = product.reviews.select_related('user').order_by(
            '-created_at'
        )[:10]
 
        reviews_serializer = ProductReviewSerializer(
            recent_reviews,
            many=True
        )
 
        return self.success_response(
            data={
                'product': serializer.data,
                'reviews': reviews_serializer.data,
                'review_count': product.total_reviews
            },
            message="Product details retrieved successfully",
            status_code=200
        )
 
 
# ============================================
# USER PRODUCTS (Inventory)
# ============================================
 
class UserProductListView(StandardResponseMixin, APIView):
    """
    List user's product inventory.
    These are products the user has scanned and added.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """
        Get user's product inventory with filtering.
 
        Query params:
        - available_only: Show only available products (default: false)
        - search: Search by product name
        """
        user = request.user
 
        # Base queryset with optimization
        queryset = UserProduct.objects.filter(user=user).select_related(
            'product'
        )
 
        # Filter by availability
        available_only = request.query_params.get('available_only', 'false').lower()
        if available_only == 'true':
            queryset = queryset.filter(is_available=True)
 
        # Search
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(product__name__icontains=search)
 
        # Order by availability and recent scans
        queryset = queryset.order_by('-is_available', '-scanned_at')
 
        serializer = UserProductSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
 
        return self.success_response(
            data={
                'products': serializer.data,
                'total_count': queryset.count(),
                'available_count': queryset.filter(is_available=True).count()
            },
            message="Inventory retrieved successfully",
            status_code=200
        )
 
    @transaction.atomic
    def post(self, request):
        """
        Add product to user inventory (simulates scanning).
        In production, this would be called after barcode scan.
        """
        serializer = CreateUserProductSerializer(
            data=request.data,
            context={'request': request}
        )
 
        if serializer.is_valid():
            user_product = serializer.save()
 
            response_serializer = UserProductSerializer(
                user_product,
                context={'request': request}
            )
 
            return self.success_response(
                data=response_serializer.data,
                message="Product added to inventory successfully",
                status_code=201
            )
 
        return self.error_response(
            "Failed to add product to inventory",
            status_code=400,
            data=serializer.errors
        )
 
 
class UserProductDetailView(StandardResponseMixin, APIView):
    """Get, update, or delete a specific product from user inventory"""
    permission_classes = [IsAuthenticated]
 
    def get_object(self, request, user_product_id):
        """Get user product"""
        try:
            return UserProduct.objects.select_related('product').get(
                id=user_product_id,
                user=request.user
            )
        except UserProduct.DoesNotExist:
            return None
 
    def get(self, request, user_product_id):
        """Get user product details"""
        user_product = self.get_object(request, user_product_id)
 
        if not user_product:
            return self.error_response(
                "Product not found in inventory",
                status_code=404
            )
 
        serializer = UserProductSerializer(
            user_product,
            context={'request': request}
        )
 
        return self.success_response(
            data=serializer.data,
            message="Product retrieved successfully",
            status_code=200
        )
 
    @transaction.atomic
    def patch(self, request, user_product_id):
        """Update user product (price or weight)"""
        user_product = self.get_object(request, user_product_id)
 
        if not user_product:
            return self.error_response(
                "Product not found in inventory",
                status_code=404
            )
 
        # Allow updating user_price and current_weight_grams
        allowed_fields = ['user_price', 'current_weight_grams']
        update_data = {
            k: v for k, v in request.data.items() if k in allowed_fields
        }
 
        serializer = UserProductSerializer(
            user_product,
            data=update_data,
            partial=True,
            context={'request': request}
        )
 
        if serializer.is_valid():
            # Update availability based on weight
            if 'current_weight_grams' in update_data:
                user_product.is_available = float(update_data['current_weight_grams']) > 0
 
            user_product = serializer.save()
 
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
    def delete(self, request, user_product_id):
        """Delete product from inventory"""
        user_product = self.get_object(request, user_product_id)
 
        if not user_product:
            return self.error_response(
                "Product not found in inventory",
                status_code=404
            )
 
        product_name = user_product.product.name
        user_product.delete()
 
        return self.success_response(
            message=f"Product '{product_name}' removed from inventory",
            status_code=200
        )
 
# ============================================
# PRODUCT REVIEWS
# ============================================
 
class ProductReviewListView(StandardResponseMixin, APIView):
    """
    Get reviews for a specific product or create new review.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request, product_id):
        """Get all reviews for a product"""
        try:
            product = ShopProduct.objects.get(id=product_id)
        except ShopProduct.DoesNotExist:
            return self.error_response(
                "Product not found",
                status_code=404
            )
 
        # Get reviews with user info
        reviews = ProductReview.objects.filter(
            product=product
        ).select_related('user').order_by('-created_at')
 
        serializer = ProductReviewSerializer(reviews, many=True)
 
        return self.success_response(
            data={
                'reviews': serializer.data,
                'total_reviews': reviews.count(),
                'average_rating': product.average_rating
            },
            message="Reviews retrieved successfully",
            status_code=200
        )
 
    @transaction.atomic
    def post(self, request, product_id):
        """Create or update review for a product"""
        # Add product_id to request data
        data = request.data.copy()
        data['product_id'] = product_id
 
        serializer = CreateProductReviewSerializer(
            data=data,
            context={'request': request}
        )
 
        if serializer.is_valid():
            review = serializer.save()
 
            response_serializer = ProductReviewSerializer(review)
 
            return self.success_response(
                data=response_serializer.data,
                message="Review submitted successfully",
                status_code=201
            )
 
        return self.error_response(
            "Failed to submit review",
            status_code=400,
            data=serializer.errors
        )
 
 
class UserReviewsView(StandardResponseMixin, APIView):
    """
    Get all reviews by the current user.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """Get user's reviews"""
        reviews = ProductReview.objects.filter(
            user=request.user
        ).select_related('product').order_by('-created_at')
 
        serializer = ProductReviewSerializer(reviews, many=True)
 
        return self.success_response(
            data={
                'reviews': serializer.data,
                'total_reviews': reviews.count()
            },
            message="Your reviews retrieved successfully",
            status_code=200
        )
 

 
# =======================================================================================================================================================
#                                                                   MIX MANAGEMENT
# ========================================================================================================================================================
 
class CheckMixCreationView(StandardResponseMixin, APIView):
    """
    Check if user can create a mix.
    Validates that user has products and clients.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """Check prerequisites for mix creation"""
        user = request.user
 
        # Check for available products
        has_products = UserProduct.objects.filter(
            user=user,
            is_available=True
        ).exists()
 
        # Check for clients
        has_clients = Client.objects.filter(user=user).exists()
 
        can_create_mix = has_products and has_clients
 
        messages = []
        if not has_products:
            messages.append("No products available. Please add products to your inventory.")
        if not has_clients:
            messages.append("No clients available. Please create a client first.")
 
        return self.success_response(
            data={
                'can_create_mix': can_create_mix,
                'has_products': has_products,
                'has_clients': has_clients,
                'messages': messages
            },
            message="Mix creation check completed",
            status_code=200
        )
 
 
class MixListCreateView(StandardResponseMixin, APIView):
    """
    List all mixes or create new mix.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """
        Get list of mixes with filtering.
 
        Query params:
        - client_id: Filter by client
        - service_type: Filter by service type
        - from_date: Filter from date (YYYY-MM-DD)
        - to_date: Filter to date (YYYY-MM-DD)
        """
        user = request.user
 
        # Base queryset with optimizations
        queryset = Mix.objects.filter(user=user).select_related(
            'client', 'user', 'sub_user'
        ).prefetch_related('mix_products')
 
        # Filter by client
        client_id = request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
 
        # Filter by service type
        service_type = request.query_params.get('service_type', '').strip()
        if service_type:
            queryset = queryset.filter(service_type__iexact=service_type)
 
        # Date range filter
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
 
        if from_date:
            queryset = queryset.filter(created_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_date__lte=to_date)
 
        # Order by most recent
        queryset = queryset.order_by('-created_date', '-created_time')
 
        serializer = MixListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
 
        return self.success_response(
            data={
                'mixes': serializer.data,
                'total_count': queryset.count()
            },
            message="Mixes retrieved successfully",
            status_code=200
        )
 
    @transaction.atomic
    def post(self, request):
        """Create new mix (without products initially)"""
        serializer = CreateMixSerializer(
            data=request.data,
            context={'request': request}
        )
 
        if serializer.is_valid():
            mix = serializer.save()
 
            detail_serializer = MixDetailSerializer(
                mix,
                context={'request': request}
            )
 
            return self.success_response(
                data=detail_serializer.data,
                message="Mix created successfully. Now add products to this mix.",
                status_code=201
            )
 
        return self.error_response(
            "Failed to create mix",
            status_code=400,
            data=serializer.errors
        )
 
 
# Continued in Part 2...
# mixapp/views.py (Part 2)
 
class MixDetailView(StandardResponseMixin, APIView):
    """
    Retrieve, update, or delete a specific mix.
    """
    permission_classes = [IsAuthenticated]
 
    def get_object(self, request, mix_id):
        """Get mix with optimized query"""
        try:
            return Mix.objects.select_related(
                'client', 'user', 'sub_user'
            ).prefetch_related(
                'mix_products__user_product__product'
            ).get(
                id=mix_id,
                user=request.user
            )
        except Mix.DoesNotExist:
            return None
 
    def get(self, request, mix_id):
        """Get mix details including all products"""
        mix = self.get_object(request, mix_id)
 
        if not mix:
            return self.error_response(
                "Mix not found",
                status_code=404
            )
 
        serializer = MixDetailSerializer(
            mix,
            context={'request': request}
        )
 
        return self.success_response(
            data=serializer.data,
            message="Mix retrieved successfully",
            status_code=200
        )
 
    @transaction.atomic
    def patch(self, request, mix_id):
        """Update mix details (name, service_type, charged_amount)"""
        mix = self.get_object(request, mix_id)
 
        if not mix:
            return self.error_response(
                "Mix not found",
                status_code=404
            )
 
        serializer = UpdateMixSerializer(
            mix,
            data=request.data,
            partial=True
        )
 
        if serializer.is_valid():
            mix = serializer.save()
 
            detail_serializer = MixDetailSerializer(
                mix,
                context={'request': request}
            )
 
            return self.success_response(
                data=detail_serializer.data,
                message="Mix updated successfully",
                status_code=200
            )
 
        return self.error_response(
            "Failed to update mix",
            status_code=400,
            data=serializer.errors
        )
 
    @transaction.atomic
    def delete(self, request, mix_id):
        """
        Delete mix.
        This will cascade delete all mix products.
        Client's total_mixes will be updated.
        """
        mix = self.get_object(request, mix_id)
 
        if not mix:
            return self.error_response(
                "Mix not found",
                status_code=404
            )
 
        client = mix.client
        mix_name = mix.mix_name
 
        # Delete mix
        mix.delete()
 
        # Update client statistics
        client.update_stats()
 
        return self.success_response(
            message=f"Mix '{mix_name}' deleted successfully",
            status_code=200
        )
 
 
class MixAddProductView(StandardResponseMixin, APIView):
    """
    Add a product to an existing mix.
    This is the main endpoint for building a mix.
    """
    permission_classes = [IsAuthenticated]
 
    @transaction.atomic
    def post(self, request, mix_id):
        """
        Add product to mix.
 
        Request body:
        - user_product_id: ID of product from user inventory
        - used_weight: Weight in grams to use
        - start_bleach_timer: Boolean (optional, for bleach products)
        """
        # Get mix
        try:
            mix = Mix.objects.select_related('client').get(
                id=mix_id,
                user=request.user
            )
        except Mix.DoesNotExist:
            return self.error_response(
                "Mix not found",
                status_code=404
            )
 
        # Validate and get product
        serializer = AddProductToMixSerializer(
            data=request.data,
            context={'request': request}
        )
 
        if not serializer.is_valid():
            return self.error_response(
                "Failed to add product to mix",
                status_code=400,
                data=serializer.errors
            )
 
        validated_data = serializer.validated_data
        user_product = validated_data['user_product']
        used_weight = validated_data['used_weight']
        start_bleach_timer = validated_data.get('start_bleach_timer', False)
 
        # Create mix product entry
        mix_product = MixProduct.objects.create(
            mix=mix,
            user_product=user_product,
            product_name=user_product.product.name,
            used_weight=used_weight,
            market_price=user_product.product.market_price,
            user_price=user_product.user_price,
            bleach_timer_started_at=timezone.now() if start_bleach_timer else None
        )
 
        # Reduce product weight in inventory
        user_product.reduce_weight(used_weight)
 
        # Recalculate mix total cost
        mix.calculate_total_cost()
 
        # Update client statistics
        mix.client.update_stats()
 
        # Return updated mix details
        mix_serializer = MixDetailSerializer(
            Mix.objects.prefetch_related('mix_products').get(id=mix.id),
            context={'request': request}
        )
 
        return self.success_response(
            data=mix_serializer.data,
            message=f"Product '{user_product.product.name}' added to mix successfully",
            status_code=201
        )
 
 
class MixRemoveProductView(StandardResponseMixin, APIView):
    """
    Remove a product from a mix.
    """
    permission_classes = [IsAuthenticated]
 
    @transaction.atomic
    def delete(self, request, mix_id, mix_product_id):
        """
        Remove product from mix.
        Note: This doesn't restore the product weight to inventory.
        """
        try:
            # Get mix
            mix = Mix.objects.get(id=mix_id, user=request.user)
 
            # Get mix product
            mix_product = MixProduct.objects.get(
                id=mix_product_id,
                mix=mix
            )
 
            product_name = mix_product.product_name
 
            # Delete mix product
            mix_product.delete()
 
            # Recalculate mix total cost
            mix.calculate_total_cost()
 
            # Update client statistics
            mix.client.update_stats()
 
            return self.success_response(
                message=f"Product '{product_name}' removed from mix",
                status_code=200
            )
 
        except Mix.DoesNotExist:
            return self.error_response(
                "Mix not found",
                status_code=404
            )
        except MixProduct.DoesNotExist:
            return self.error_response(
                "Product not found in mix",
                status_code=404
            )
 
 
class MixStatsView(StandardResponseMixin, APIView):
    """
    Get mix statistics for dashboard.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """Get aggregated mix statistics"""
        user = request.user
 
        # Get current month
        now = timezone.now()
        first_day_of_month = now.replace(day=1).date()
 
        # All mixes
        all_mixes = Mix.objects.filter(user=user)
 
        # Aggregate statistics
        totals = all_mixes.aggregate(
            total_profit=Sum('profit'),
            total_revenue=Sum('charged_amount'),
            total_cost=Sum('total_cost')
        )
 
        # Most used service type
        most_used_service = all_mixes.values('service_type').annotate(
            count=Count('id')
        ).order_by('-count').first()
 
        stats = {
            'total_mixes': all_mixes.count(),
            'total_profit': totals['total_profit'] or 0,
            'total_revenue': totals['total_revenue'] or 0,
            'total_cost': totals['total_cost'] or 0,
            'mixes_this_month': all_mixes.filter(
                created_date__gte=first_day_of_month
            ).count(),
            'most_used_service_type': most_used_service['service_type'] if most_used_service else 'N/A'
        }
 
        serializer = MixStatsSerializer(data=stats)
        serializer.is_valid()
 
        return self.success_response(
            data=serializer.data,
            message="Mix statistics retrieved successfully",
            status_code=200
        )
 
 

 
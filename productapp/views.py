from django.shortcuts import render
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
# Create your views here.
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
 
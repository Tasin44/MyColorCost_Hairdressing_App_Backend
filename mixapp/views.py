from django.shortcuts import render

# Create your views here.
# mixapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, serializers
from rest_framework.viewsets import ModelViewSet
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from rest_framework.decorators import action
from .models import ShopProduct, UserProduct, Mix, MixProduct, ProductReview,ProductScanHistory
from clientapp.models import Client
from .serializers import (
    ShopProductListSerializer, ShopProductDetailSerializer,
    UserProductSerializer, CreateUserProductSerializer,
    MixListSerializer, MixDetailSerializer, CreateMixSerializer,
    UpdateMixSerializer, AddProductToMixSerializer,
    MixProductSerializer, ProductReviewSerializer,
    CreateProductReviewSerializer, MixStatsSerializer,AssignClientSerializer,
    SetChargedAmountSerializer, BarcodeScanRequestSerializer,
    BarcodeScanResponseSerializer, ManualProductEntrySerializer,
    UpdateScannedProductSerializer
)
from mixapp.utils import generate_mix_pdf
 
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

         # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user

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

        '''
        # Order by availability and recent scans
        queryset = queryset.order_by('-is_available', '-scanned_at')
 
        serializer = UserProductSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        '''
     # ✅ Build response with conditional scanned_at
        data = []
        for user_product in queryset:
            product_data = {
                'id': user_product.id,
                'product_id': user_product.product.id,
                'product_name': user_product.product.name,
                'product_image': request.build_absolute_uri(user_product.product.image.url) if user_product.product.image else None,
                'market_price': str(user_product.product.market_price),
                'user_price': str(user_product.user_price) if user_product.user_price else None,
                'current_weight_grams': str(user_product.current_weight_grams),
                'is_available': user_product.is_available,
                'last_used_at': user_product.last_used_at.isoformat() if user_product.last_used_at else None
            }
            
            # ✅ Check if manual entry (has scan history with manual type)
            is_manual = ProductScanHistory.objects.filter(
                shop_product=user_product.product,
                user=owner,
                scan_type='manual'
            ).exists()
            
            # ✅ Add scanned_at ONLY if NOT manual entry
            if not is_manual:
                product_data['scanned_at'] = user_product.scanned_at.isoformat()
                product_data['api_data'] = user_product.product.api_data  # ✅ Full Barcode Spider data
            
            data.append(product_data)
 
        return self.success_response(
            data={
                'products': data,
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
        # ✅ FIX: Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        # Check for available products (owner's products)
        has_products = UserProduct.objects.filter(
            user=owner,
            is_available=True
        ).exists()
        
        # Check for clients (owner's clients)
        has_clients = Client.objects.filter(user=owner).exists()

        '''
        #previously I was checking logged in user, but now checking owner, whether he is staff or owner
        # Check for available products
        has_products = UserProduct.objects.filter(
            user=user,
            is_available=True
        ).exists()
 
        # Check for clients
        has_clients = Client.objects.filter(user=user).exists()
        
        '''
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

        # ✅ FIX: Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
        
            # ✅ Staff sees ONLY their own mixes
            queryset = Mix.objects.filter(
                user=owner,
                sub_user=staff_profile  # ✅ Only this staff's mixes
            ).select_related('client', 'user', 'sub_user').prefetch_related('mix_products')
        else:
            owner = user
        
        # Base queryset - filter by owner
        queryset = Mix.objects.filter(user=owner).select_related(
            'client', 'user', 'sub_user'
        ).prefetch_related('mix_products')

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

        '''
        if from_date:
            queryset = queryset.filter(created_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_date__lte=to_date)
        '''
        if from_date:
            queryset = queryset.filter(created_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_at__date__lte=to_date)
 
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
            user = request.user
            
            # ✅ FIX: Determine owner and sub_user
            if user.role == 'staff' and hasattr(user, 'staff_profile'):
                staff_profile = user.staff_profile
                owner = staff_profile.main_user
                sub_user = staff_profile
            else:
                owner = user
                sub_user = None
            
            # Create mix
            mix = Mix.objects.create(
                user=owner,  # ✅ Owner gets the mix
                #sub_user=sub_user,  # ✅ Staff is tracked
                #sub_user=staff_profile,  # ✅ SubUser object (has .user FK to actual User)
                sub_user=sub_user,  # ✅ Use sub_user, not staff_profile
                **serializer.validated_data
            )            
            
            
            #mix = serializer.save()
            # ✅ KEEP ONLY THIS - save with correct user and sub_user
            #mix = serializer.save(user=owner, sub_user=sub_user)
 
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
    
    '''
    def get_object(self, request, mix_id):
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
    '''
    def get_object(self, request, mix_id):
        """Get mix - staff can only access their own mixes, owner sees all"""
        user = request.user
        
        # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
            
            # Staff can only access mixes they created
            try:
                return Mix.objects.select_related(
                    'client', 'user', 'sub_user'
                ).prefetch_related(
                    'mix_products__user_product__product'
                ).get(
                    id=mix_id,
                    user=owner,
                    sub_user=staff_profile  # ✅ Only their mixes
                )
            except Mix.DoesNotExist:
                return None
        else:
            # Owner sees all mixes
            try:
                return Mix.objects.select_related(
                    'client', 'user', 'sub_user'
                ).prefetch_related(
                    'mix_products__user_product__product'
                ).get(
                    id=mix_id,
                    user=user
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
 
        # ✅ FIX: Only update stats if client exists
        if client: #without checking , I got - 'NoneType' object has no attribute 'update_stats'
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
        user = request.user
        
        # ✅ FIX: Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        # Get mix (must belong to owner)
        try:
            mix = Mix.objects.select_related('client').get(
                id=mix_id,
                # user=request.user
                user=owner  # ✅ Check against owner
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
        # start_bleach_timer = validated_data.get('start_bleach_timer', False)
        # market_price = validated_data['market_price']
        # ✅ AUTO-FETCH market_price if not provided
        market_price = validated_data.get('market_price')
        if not market_price:
            market_price = user_product.product.market_price
        user_price = validated_data['user_price']  # ✅ GET FROM REQUEST


        #charged_amount = validated_data['charged_amount']
        # start_bleach_timer = validated_data.get('start_bleach_timer', False)
        is_bleach_timer_on = validated_data['is_bleach_timer_on']
        bleach_timer_start_time = validated_data.get('bleach_timer_start_time')
        bleach_timer_duration = validated_data.get('bleach_timer_duration')
        # Create mix product entry
        mix_product = MixProduct.objects.create(
            mix=mix,
            user_product=user_product,
            product_name=user_product.product.name,
            used_weight=used_weight,
            # market_price=user_product.product.market_price,
            market_price=market_price,   # ✅ USE REQUEST VALUE

            #❌STOP reading user_price from inventory
            #user_price=user_product.user_price,

            user_price=user_price,  # ✅ USE REQUEST VALUE
            
            #bleach_timer_started_at=timezone.now().isoformat()
            #bleach_timer_started_at=timezone.now()
            is_bleach_timer_on=is_bleach_timer_on,
            bleach_timer_start_time=bleach_timer_start_time if is_bleach_timer_on else None,
            bleach_timer_duration=bleach_timer_duration if is_bleach_timer_on else None
        )
        #mix.charged_amount = charged_amount

        # mix.save(update_fields=['charged_amount', 'updated_at'])  # ✅ Specify fields
        mix.save(update_fields=['updated_at'])  # ✅ Specify fields
        # Reduce product weight in inventory
        user_product.reduce_weight(used_weight)


        # Recalculate mix total cost
        mix.calculate_total_cost()
 
        # Update client statistics
        #mix.client.update_stats()
        if mix.client:  # ✅ Add this check
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
    
    '''
    @transaction.atomic
    def delete(self, request, mix_id, mix_product_id):
        # """
        # Remove product from mix.
        # Note: This doesn't restore the product weight to inventory.
        # """
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
    
    '''
    @transaction.atomic
    def delete(self, request, mix_id, mix_product_id):
        user = request.user
        
        # Get correct owner and check permissions
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
            
            try:
                # Staff can only delete from their own mixes
                mix = Mix.objects.get(id=mix_id, user=owner, sub_user=staff_profile)
            except Mix.DoesNotExist:
                return self.error_response("Mix not found", status_code=404)
        else:
            # Owner can delete from any mix
            try:
                mix = Mix.objects.get(id=mix_id, user=user)
            except Mix.DoesNotExist:
                return self.error_response("Mix not found", status_code=404)
        
        # Get mix product
        try:
            mix_product = MixProduct.objects.get(id=mix_product_id, mix=mix)
        except MixProduct.DoesNotExist:
            return self.error_response("Product not found in mix", status_code=404)
        
        product_name = mix_product.product_name
        mix_product.delete()
        mix.calculate_total_cost()
        
        if mix.client:
            mix.client.update_stats()
        
        return self.success_response(
            message=f"Product '{product_name}' removed from mix",
            status_code=200
        )
 
'''
class MixStatsView(StandardResponseMixin, APIView):

    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        user = request.user
 
        # Get current month
       # now = timezone.now().isoformat()
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
 
 
'''
class MixStatsView(StandardResponseMixin, APIView):
    """
    Get mix statistics for dashboard.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        """Get aggregated mix statistics"""
        user = request.user
        now = timezone.now()
        first_day_of_month = now.replace(day=1).date()
 
        # ✅ Determine which mixes to include
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            # Staff sees only their own mixes
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
            all_mixes = Mix.objects.filter(user=owner, sub_user=staff_profile)
        else:
            # Owner sees all mixes (own + all staff)
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

class MixViewSet(ModelViewSet):
    queryset = Mix.objects.all()
    serializer_class = CreateMixSerializer

    @action(detail=True, methods=['post'], url_path='assign-client')
    def assign_client(self, request, pk=None):

        user = request.user
        
        # ✅ FIX: Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
        else:
            owner = user
            staff_profile = None


        mix = self.get_object()
        serializer = AssignClientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client_id = serializer.validated_data['client_id']

        try:
            client = Client.objects.get(
                id=client_id,
                #user=request.user
                user=owner  # ✅ Check against owner, not request.user
            )
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        mix.client = client
        mix.save(update_fields=['client'])

        return Response(
            {
                "message": "Client assigned to mix successfully",
                "mix_id": mix.id,
                "client_id": client.id
            },
            status=status.HTTP_200_OK
        )
    


class MixGeneratePDFView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mix_id):
        mix = Mix.objects.prefetch_related("mix_products").filter(id=mix_id).first()
        if not mix:
            return self.error_response("Mix not found", 404)

        pdf_url = generate_mix_pdf(mix)
        mix.pdf_url = pdf_url
        mix.save(update_fields=["pdf_url"])

        return self.success_response(
            data={"pdf_url": pdf_url},
            message="PDF generated successfully",
            status_code=200
        )


class MixSetChargedAmountView(StandardResponseMixin, APIView):
    """Set charged amount for a mix and calculate profit"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def patch(self, request, mix_id):
        user = request.user
        
        # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
            try:
                mix = Mix.objects.get(id=mix_id, user=owner, sub_user=staff_profile)
            except Mix.DoesNotExist:
                return self.error_response("Mix not found", status_code=404)
        else:
            try:
                mix = Mix.objects.get(id=mix_id, user=user)
            except Mix.DoesNotExist:
                return self.error_response("Mix not found", status_code=404)
        
        serializer = SetChargedAmountSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self.error_response(
                "Invalid data",
                status_code=400,
                data=serializer.errors
            )
        
        charged_amount = serializer.validated_data['charged_amount']
        mix.charged_amount = charged_amount
        mix.calculate_profit()
        mix.save(update_fields=['charged_amount', 'profit', 'updated_at'])
        
        detail_serializer = MixDetailSerializer(mix, context={'request': request})
        
        return self.success_response(
            data=detail_serializer.data,
            message="Charged amount set successfully",
            status_code=200
        )


#---------------------------------------------------------------
class ScanBarcodeView(StandardResponseMixin, APIView):
    """
    Scan barcode and retrieve product information
    Flow:
    1. Check if product exists in our database
    2. If not, query Barcode Spider API
    3. If found in API, create ShopProduct
    4. If not found anywhere, return manual_entry_required flag
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """
        Scan barcode and get product info
        
        Request body:
        - barcode: Scanned barcode/UPC string
        
        Response:
        - found_in_db: bool (product exists in database)
        - found_in_api: bool (product found via Barcode Spider)
        - manual_entry_required: bool (need manual entry)
        - product: Product data if found
        - message: Status message
        """
        # Validate request
        serializer = BarcodeScanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                "Invalid barcode data",
                status_code=400,
                data=serializer.errors
            )
        
        barcode = serializer.validated_data['barcode']
        user = request.user
        
        # Get correct owner (for staff users)
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # Step 1: Check if product already exists in our database
        try:
            shop_product = ShopProduct.objects.get(barcode=barcode)
            
            # Product found in DB
            # Create scan history
            ProductScanHistory.objects.create(
                user=owner,
                shop_product=shop_product,
                barcode=barcode,
                scan_type='barcode'
            )
            
            response_data = {
                'found_in_db': True,
                'found_in_api': False,
                'manual_entry_required': False,
                'product': shop_product,
                'message': 'Product found in database'
            }
            
            response_serializer = BarcodeScanResponseSerializer(
                response_data,
                context={'request': request}
            )
            
            return self.success_response(
                data=response_serializer.data,
                message="Product found in database",
                status_code=200
            )
            
        except ShopProduct.DoesNotExist:
            # Product not in DB, try Barcode Spider API
            pass
        
        # Step 2: Query Barcode Spider API
        from .barcode_utils import barcode_api
        
        api_result = barcode_api.lookup_barcode(barcode)
        
        if api_result:
            # Product found in API
            # Create ShopProduct from API data
            # ✅ CHANGED: Store full API response
            shop_product = ShopProduct.objects.create(
                name=api_result['name'],
                description=api_result.get('description', ''),
                barcode=barcode,
                market_price=Decimal('0.00'),
                average_rating=Decimal('0.00'),
                total_reviews=0,
                api_data=api_result.get('raw_data')  # ✅ ADD THIS - stores full JSON
            )
            
            # Create scan history
            ProductScanHistory.objects.create(
                user=owner,
                shop_product=shop_product,
                barcode=barcode,
                scan_type='barcode'
            )

            # # ✅ FIX: Check if price/weight exist in API response
            # stores = api_result['raw_data'].get('Stores', [])
            # has_price = any(store.get('price') for store in stores)  # Check if any store has price
            # has_weight = bool(api_result.get('weight', '').strip())  # Check if weight exists
            # ✅ FIX: Check if price/weight exist in API response
            raw_data = api_result.get('raw_data', {})
            stores = raw_data.get('Stores', [])
            
            # Check if ANY store has a non-empty price
            has_price = any(
                store.get('price', '').strip() 
                for store in stores
            )
            
            # Check if weight exists and is not empty
            weight = api_result.get('weight', '').strip()
            has_weight = bool(weight)
            # ✅ Return FULL API response
            response_data = {
                'found_in_db': False,
                'found_in_api': True,
                'manual_entry_required': not (has_price and has_weight),  # ✅ Only if missing data
                'product': {
                    'id': shop_product.id,
                    'name': api_result['name'],
                    'description': api_result.get('description', ''),
                    'barcode': barcode,
                    'brand': api_result.get('brand', ''),
                    'manufacturer': api_result.get('manufacturer', ''),
                    'category': api_result.get('category', ''),
                    'image_url': api_result.get('image_url', ''),
                    'weight': api_result.get('weight', ''),
                    'model': api_result.get('model', ''),
                    'asin': api_result.get('asin', ''),
                    'mpn': api_result.get('mpn', ''),
                    'upc': api_result.get('upc', ''),
                    'ean': api_result.get('ean', ''),
                    'color': api_result.get('color', ''),
                    'size': api_result.get('size', ''),
                    'stores': api_result['raw_data'].get('Stores', []),  # ✅ Store info
                    'needs_price': not has_price,      # ✅ TRUE only if empty/missing
                    'needs_weight': not has_weight
                },
                'message': 'Product found. Please enter price and weight if missing.'
            }
            
            response_serializer = BarcodeScanResponseSerializer(
                response_data,
                context={'request': request}
            )
            
            return self.success_response(
                data=response_serializer.data,
                message="Product found in API. Please complete product details.",
                status_code=200
            )
        
        # Step 3: Product not found anywhere - require manual entry
        response_data = {
            'found_in_db': False,
            'found_in_api': False,
            'manual_entry_required': True,
            'product': None,
            'message': 'Product not found. Please enter product details manually.'
        }
        
        response_serializer = BarcodeScanResponseSerializer(
            response_data,
            context={'request': request}
        )
        
        return self.success_response(
            data=response_serializer.data,
            message="Product not found. Manual entry required.",
            status_code=200
        )


class ManualProductEntryView(StandardResponseMixin, APIView):
    """
    Manually create product and add to inventory
    Used when barcode scan doesn't find product
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Add this line

    @transaction.atomic
    def post(self, request):
        """
        Create product manually and add to user inventory
        
        Request body:
        - name: Product name (required)
        - description: Product description
        - market_price: Price per 100g (required)
        - current_weight_grams: Initial weight (required)
        - barcode: Barcode if available
        - image: Product image
        - expiry_date: Expiry date
        """
        serializer = ManualProductEntrySerializer(data=request.data)
        
        if not serializer.is_valid():
            return self.error_response(
                "Invalid product data",
                status_code=400,
                data=serializer.errors
            )
        
        validated_data = serializer.validated_data
        user = request.user
        
        # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # Check if barcode already exists
        barcode = validated_data.get('barcode')
        if barcode:
            if ShopProduct.objects.filter(barcode=barcode).exists():
                return self.error_response(
                    "Product with this barcode already exists",
                    status_code=400
                )
        
        # Create ShopProduct
        '''
        
        '''
        shop_product = ShopProduct.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            market_price=validated_data['market_price'],
            barcode=barcode,
            image=validated_data.get('image'),
            expiry_date=validated_data.get('expiry_date'),
            average_rating=Decimal('0.00'),
            total_reviews=0
        )
        
        # Add to user inventory (UserProduct)
        user_product = UserProduct.objects.create(
            user=owner,
            product=shop_product,
            user_price=validated_data['market_price'],  # Default to market price
            current_weight_grams=validated_data['current_weight_grams'],
            is_available=True
        )
        
        # Create scan history
        
        ProductScanHistory.objects.create(
            user=owner,
            shop_product=shop_product,
            barcode=barcode if barcode else None,
            scanned_weight=validated_data['current_weight_grams'],
            scan_type='manual'
        )
        

        
        # Prepare response
        product_serializer = ShopProductDetailSerializer(
            shop_product,
            context={'request': request}
        )
        
        inventory_serializer = UserProductSerializer(
            user_product,
            context={
                
                'request': request,
                 'is_manual_entry': True  # ✅ ADD THIS FLAG    
                     
                }
        )
        
        return self.success_response(
            data={
                'shop_product': product_serializer.data,
                'user_product': inventory_serializer.data
            },
            message="Product created and added to inventory successfully",
            status_code=201
        )

class UpdateScannedProductView(StandardResponseMixin, APIView):
    """
    Update scanned product with manual price and weight
    Used after scanning when Barcode Spider doesn't return complete data
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def patch(self, request, product_id):
        """
        Update ShopProduct and optionally create/update UserProduct
        
        Request body:
        - market_price: Price per 100g (updates ShopProduct)
        - current_weight_grams: Initial weight (creates/updates UserProduct)
        - user_price: Optional custom price per 100g
        """
        user = request.user
        
        # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # Get shop product
        try:
            shop_product = ShopProduct.objects.get(id=product_id)
        except ShopProduct.DoesNotExist:
            return self.error_response(
                "Product not found",
                status_code=404
            )
        
        # Validate request
        serializer = UpdateScannedProductSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                "Invalid data",
                status_code=400,
                data=serializer.errors
            )
        
        validated_data = serializer.validated_data

        updated_fields = {}
        
        # ✅ Update ShopProduct market_price if provided
        if 'market_price' in validated_data:
            if shop_product.market_price == Decimal('0.00'):
                shop_product.market_price = validated_data['market_price']
                shop_product.save(update_fields=['market_price', 'updated_at'])
                updated_fields['market_price'] = str(validated_data['market_price'])
            else:
                return self.error_response(
                    "Market price already set. Cannot update.",
                    status_code=400
                )
        
        # ✅ Step 2: Create/Update UserProduct with weight
        if 'current_weight_grams' in validated_data:
            # Determine user_price
            user_price = validated_data.get('user_price')
            if not user_price:
                # Default to market_price if not provided
                user_price = validated_data.get('market_price', shop_product.market_price)
            
            # Check if UserProduct exists
            try:
                user_product = UserProduct.objects.get(user=owner, product=shop_product)
                
                # ✅ Update existing - ADD weight
                user_product.current_weight_grams = validated_data['current_weight_grams']
                if 'user_price' in validated_data:
                    user_product.user_price = validated_data['user_price']
                user_product.is_available = user_product.current_weight_grams > 0
                user_product.save(update_fields=[
                    'user_price', 'current_weight_grams', 'is_available'
                ])
                
                updated_fields['user_product_id'] = user_product.id
                updated_fields['current_weight_grams'] = str(user_product.current_weight_grams)
                updated_fields['user_price'] = str(user_product.user_price)
                
            except UserProduct.DoesNotExist:
                # ✅ Create new UserProduct
                user_product = UserProduct.objects.create(
                    user=owner,
                    product=shop_product,
                    user_price=user_price,
                    current_weight_grams=validated_data['current_weight_grams'],
                    is_available=True
                )
                
                updated_fields['user_product_id'] = user_product.id
                updated_fields['current_weight_grams'] = str(user_product.current_weight_grams)
                updated_fields['user_price'] = str(user_product.user_price)
        
        # ✅ Step 3: Return ONLY updated fields + product_id
        if not updated_fields:
            return self.error_response(
                "No fields were updated. Provide at least one field to update.",
                status_code=400
            )
        
        return self.success_response(
            data={
                'product_id': product_id,
                'updated_fields': updated_fields
            },
            message="Product updated successfully",
            status_code=200
        )


class ProductScanHistoryView(StandardResponseMixin, APIView):
    """
    Get scan history for products
    Shows all products scanned by the user/owner
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get scan history with filters
        
        Query params:
        - scan_type: Filter by scan type (barcode/qr/manual)
        - from_date: Filter from date (YYYY-MM-DD)
        - to_date: Filter to date (YYYY-MM-DD)
        - limit: Number of results (default: 50)
        """
        user = request.user
        
        # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # Base queryset
        queryset = ProductScanHistory.objects.filter(
            user=owner
        ).select_related('shop_product').order_by('-created_at')
        
        # Filter by scan type
        scan_type = request.query_params.get('scan_type')
        if scan_type in ['barcode', 'qr', 'manual']:
            queryset = queryset.filter(scan_type=scan_type)
        
        # Date filters
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        if from_date:
            queryset = queryset.filter(created_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_at__date__lte=to_date)
        
        # Limit results
        limit = int(request.query_params.get('limit', 50))
        queryset = queryset[:limit]
        
        # Serialize data
        data = []
        for scan in queryset:
            data.append({
                'id': scan.id,
                'product': {
                    'id': scan.shop_product.id,
                    'name': scan.shop_product.name,
                    'barcode': scan.shop_product.barcode,
                    'market_price': str(scan.shop_product.market_price),
                    'image_url': request.build_absolute_uri(scan.shop_product.image.url) if scan.shop_product.image else None,
                    'api_data': scan.shop_product.api_data  # Full Barcode Spider response
                },
                '''
                'scan_details': {
                    'barcode': scan.barcode,
                    'qr_code': scan.qr_code,
                    'scanned_weight': str(scan.scanned_weight) if scan.scanned_weight else None,
                    'scan_type': scan.scan_type
                },
                '''

                'scanned_at': scan.created_at.isoformat()
            })
        
        return self.success_response(
            data={
                'scans': data,
                'total_count': len(data)
            },
            message="Scan history retrieved successfully",
            status_code=200
        )




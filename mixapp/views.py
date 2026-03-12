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
from .models import ShopProduct, UserProduct, Mix, MixProduct, ProductReview, ProductScanHistory, ShoppingCart
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
 
#it was previous
# class ShopProductListView(StandardResponseMixin, APIView):
#     """
#     List all shop products with search and filtering.
#     These are products that can be scanned and added to inventory.
#     """
#     permission_classes = [IsAuthenticated]
 
#     def get(self, request):
#         """
#         Get product list with optional filtering.
 
#         Query params:
#         - search: Search by name or retailer
#         - min_rating: Filter by minimum rating
#         - retailer: Filter by retailer name
#         """
#         queryset = ShopProduct.objects.all()
 
#         # Search
#         search = request.query_params.get('search', '').strip()
#         if search:
#             queryset = queryset.filter(
#                 Q(name__icontains=search) |
#                 Q(retailer_name__icontains=search)
#             )
 
#         # Filter by rating
#         min_rating = request.query_params.get('min_rating')
#         if min_rating:
#             try:
#                 queryset = queryset.filter(average_rating__gte=float(min_rating))
#             except ValueError:
#                 pass
 
#         # Filter by retailer
#         retailer = request.query_params.get('retailer', '').strip()
#         if retailer:
#             queryset = queryset.filter(retailer_name__iexact=retailer)
 
#         # Order by rating and name
#         queryset = queryset.order_by('-average_rating', 'name')
 
#         serializer = ShopProductListSerializer(
#             queryset,
#             many=True,
#             context={'request': request}
#         )
 
#         return self.success_response(
#             data={
#                 'products': serializer.data,
#                 'total_count': queryset.count()
#             },
#             message="Products retrieved successfully",
#             status_code=200
#         )
 
#newly added
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
        - stock_status: Filter by stock status (NEW)
        - retailer_id: Filter by retailer ID (NEW)
        """
        # ✅ ADD select_related for optimization
        #queryset = ShopProduct.objects.select_related('retailer').order_by('-average_rating', 'name')

         # ✅ ADD: Only show retailer-uploaded products (exclude scanned/manual entry products) + etailer who connected with stripe 
        queryset = ShopProduct.objects.select_related('retailer').filter(
            retailer__isnull=False,
            retailer__is_approved=True,
            retailer__stripe_connected=True  # ✅ ADD THIS
        ).order_by('-average_rating', 'name')

        # ✅ FIX: Search by name or retailer business name
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(retailer__business_name__icontains=search)  # ✅ FIXED
            )
 
        # Filter by rating
        min_rating = request.query_params.get('min_rating')
        if min_rating:
            try:
                queryset = queryset.filter(average_rating__gte=float(min_rating))
            except ValueError:
                pass
 
        # ✅ FIX: Filter by retailer business name
        retailer = request.query_params.get('retailer', '').strip()
        if retailer:
            queryset = queryset.filter(retailer__business_name__iexact=retailer)  # ✅ FIXED
        
        # ✅ NEW: Filter by stock status
        stock_status = request.query_params.get('stock_status')
        if stock_status in ['in_stock', 'out_of_stock', 'low_stock']:
            queryset = queryset.filter(stock_status=stock_status)
        
        # ✅ NEW: Filter by retailer ID
        retailer_id = request.query_params.get('retailer_id')
        if retailer_id:
            queryset = queryset.filter(retailer_id=retailer_id)
 
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

#it was previous
# class ShopProductDetailView(StandardResponseMixin, APIView):
#     """Get detailed information about a specific product"""
#     permission_classes = [IsAuthenticated]
 
#     def get(self, request, product_id):
#         """Get product details including reviews"""
#         try:
#             product = ShopProduct.objects.prefetch_related('reviews').get(
#                 id=product_id
#             )
#         except ShopProduct.DoesNotExist:
#             return self.error_response(
#                 "Product not found",
#                 status_code=404
#             )
 
#         # Get product details
#         serializer = ShopProductDetailSerializer(
#             product,
#             context={'request': request}
#         )
 
#         # Get recent reviews
#         recent_reviews = product.reviews.select_related('user').order_by(
#             '-created_at'
#         )[:10]
 
#         reviews_serializer = ProductReviewSerializer(
#             recent_reviews,
#             many=True
#         )
 
#         return self.success_response(
#             data={
#                 'product': serializer.data,
#                 'reviews': reviews_serializer.data,
#                 'review_count': product.total_reviews
#             },
#             message="Product details retrieved successfully",
#             status_code=200
#         )
 

#newly added 
class ShopProductDetailView(StandardResponseMixin, APIView):
    """Get detailed information about a specific product"""
    permission_classes = [IsAuthenticated]
 
    def get(self, request, product_id):
        """
        Get product details including reviews.
        Now also includes retailer info and delivery areas.
        """
        try:
            # ✅ Optimized query - handles NULL retailer gracefully
            product = ShopProduct.objects.select_related(
                'retailer'
            ).prefetch_related(
                'reviews__user',  # ✅ KEEP existing reviews prefetch
                'retailer__delivery_areas'  # ✅ NEW: Add delivery areas
            ).get(id=product_id)
            
        except ShopProduct.DoesNotExist:
            return self.error_response(
                "Product not found",
                status_code=404
            )
 
        # ✅ EXISTING: Get product details
        serializer = ShopProductDetailSerializer(
            product,
            context={'request': request}
        )
 
        # ✅ EXISTING: Get recent reviews
        recent_reviews = product.reviews.select_related('user').order_by(
            '-created_at'
        )[:10]
 
        reviews_serializer = ProductReviewSerializer(
            recent_reviews,
            many=True
        )
 
        # ✅ KEEP existing response structure
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
        queryset = UserProduct.objects.filter(user=owner).select_related(
            'product'
        )
        '''
        if I use here user=user, it'll cause issue on the product list, the updated weight won't be visible there, because during updating, I'm doing update for owner(even if the user is staff)
        If you're staff, user != owner, so after updating with owner, the GET still queries with user (the staff user) and finds nothing updated.

        this  is the place in scanproductview
        user_product = UserProduct.objects.get(user=owner, product=shop_product)
        '''
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
        """Create new mix with products in one request"""
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
                message="Mix created successfully with all products",
                status_code=201
            )
 
        return self.error_response(
            "Failed to create mix",
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
        #can_create_mix = has_products and has_clients
 
        messages = []
        if not has_products:
            messages.append("No products available. Please add products to your inventory.")
        if not has_clients:
            messages.append("No clients available. Please create a client first.")
 
        return self.success_response(
            data={
                'can_create_mix': True,# ✅ ALWAYS TRUE
                'has_products': has_products,
                'has_clients': has_clients,
                'messages': messages,
                'allow_empty_mix': True  # ✅ Signal to frontend
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
    
    #previous 
    '''
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

    '''
    @transaction.atomic
    def post(self, request):
        """Create new mix with products"""
        serializer = CreateMixSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            mix = serializer.save()  # ✅ Use serializer.save() instead of Mix.objects.create()
            
            detail_serializer = MixDetailSerializer(mix, context={'request': request})
            
            return self.success_response(
                data=detail_serializer.data,
                message="Mix created successfully with products.",
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
        #user_price = validated_data['user_price']  # ✅ GET FROM REQUEST
        # USE THIS INSTEAD:
        user_price = user_product.user_price  # ← always per 100g, never changes

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

#my previous working code 
# class ScanBarcodeView(StandardResponseMixin, APIView):
#     """
#     Scan barcode and retrieve product information
#     Flow:
#     1. Check if product exists in our database
#     2. If not, query Barcode Spider API
#     3. If found in API, create ShopProduct
#     4. If not found anywhere, return manual_entry_required flag
#     """
#     permission_classes = [IsAuthenticated]
    
#     @transaction.atomic
#     def post(self, request):
#         """
#         Scan barcode and get product info
        
#         Request body:
#         - barcode: Scanned barcode/UPC string
        
#         Response:
#         - found_in_db: bool (product exists in database)
#         - found_in_api: bool (product found via Barcode Spider)
#         - manual_entry_required: bool (need manual entry)
#         - product: Product data if found
#         - message: Status message
#         """
#         # Validate request
#         serializer = BarcodeScanRequestSerializer(data=request.data)
#         if not serializer.is_valid():
#             return self.error_response(
#                 "Invalid barcode data",
#                 status_code=400,
#                 data=serializer.errors
#             )
        
#         barcode = serializer.validated_data['barcode']
#         user = request.user
        
#         # Get correct owner (for staff users)
#         if user.role == 'staff' and hasattr(user, 'staff_profile'):
#             owner = user.staff_profile.main_user
#         else:
#             owner = user
        
#         # Step 1: Check if product already exists in our database
#         try:
#             shop_product = ShopProduct.objects.get(barcode=barcode)
            
#             # Product found in DB
#             # Create scan history
#             ProductScanHistory.objects.create(
#                 user=owner,
#                 shop_product=shop_product,
#                 barcode=barcode,
#                 scan_type='barcode'
#             )
            
#             response_data = {
#                 'found_in_db': True,
#                 'found_in_api': False,
#                 'manual_entry_required': False,
#                 'product': shop_product,
#                 'message': 'Product found in database'
#             }
            
#             response_serializer = BarcodeScanResponseSerializer(
#                 response_data,
#                 context={'request': request}
#             )
            
#             return self.success_response(
#                 data=response_serializer.data,
#                 message="Product found in database",
#                 status_code=200
#             )
            
#         except ShopProduct.DoesNotExist:
#             # Product not in DB, try Barcode Spider API
#             pass
        
#         # Step 2: Query Barcode Spider API
#         from .barcode_utils import barcode_api
        
#         api_result = barcode_api.lookup_barcode(barcode)
        
#         if api_result:
#             # Product found in API
#             # Create ShopProduct from API data
#             # ✅ CHANGED: Store full API response
#             shop_product = ShopProduct.objects.create(
#                 name=api_result['name'],
#                 description=api_result.get('description', ''),
#                 barcode=barcode,
#                 market_price=Decimal('0.00'),
#                 average_rating=Decimal('0.00'),
#                 total_reviews=0,
#                 api_data=api_result.get('raw_data')  # ✅ ADD THIS - stores full JSON
#             )
            
#             # Create scan history
#             ProductScanHistory.objects.create(
#                 user=owner,
#                 shop_product=shop_product,
#                 barcode=barcode,
#                 scan_type='barcode'
#             )

#             # # ✅ FIX: Check if price/weight exist in API response
#             # stores = api_result['raw_data'].get('Stores', [])
#             # has_price = any(store.get('price') for store in stores)  # Check if any store has price
#             # has_weight = bool(api_result.get('weight', '').strip())  # Check if weight exists
#             # ✅ FIX: Check if price/weight exist in API response
#             raw_data = api_result.get('raw_data', {})
#             stores = raw_data.get('Stores', [])
            
#             # Check if ANY store has a non-empty price
#             has_price = any(
#                 store.get('price', '').strip() 
#                 for store in stores
#             )
            
#             # Check if weight exists and is not empty
#             weight = api_result.get('weight', '').strip()
#             has_weight = bool(weight)
#             # ✅ Return FULL API response
#             response_data = {
#                 'found_in_db': False,
#                 'found_in_api': True,
#                 'manual_entry_required': not (has_price and has_weight),  # ✅ Only if missing data
#                 'product': {
#                     'id': shop_product.id,
#                     'name': api_result['name'],
#                     'description': api_result.get('description', ''),
#                     'barcode': barcode,
#                     'brand': api_result.get('brand', ''),
#                     'manufacturer': api_result.get('manufacturer', ''),
#                     'category': api_result.get('category', ''),
#                     'image_url': api_result.get('image_url', ''),
#                     'weight': api_result.get('weight', ''),
#                     'model': api_result.get('model', ''),
#                     'asin': api_result.get('asin', ''),
#                     'mpn': api_result.get('mpn', ''),
#                     'upc': api_result.get('upc', ''),
#                     'ean': api_result.get('ean', ''),
#                     'color': api_result.get('color', ''),
#                     'size': api_result.get('size', ''),
#                     'stores': api_result['raw_data'].get('Stores', []),  # ✅ Store info
#                     'needs_price': not has_price,      # ✅ TRUE only if empty/missing
#                     'needs_weight': not has_weight
#                 },
#                 'message': 'Product found. Please enter price and weight if missing.'
#             }
            
#             response_serializer = BarcodeScanResponseSerializer(
#                 response_data,
#                 context={'request': request}
#             )
            
#             return self.success_response(
#                 data=response_serializer.data,
#                 message="Product found in API. Please complete product details.",
#                 status_code=200
#             )
        
#         # Step 3: Product not found anywhere - require manual entry
#         response_data = {
#             'found_in_db': False,
#             'found_in_api': False,
#             'manual_entry_required': True,
#             'product': None,
#             'message': 'Product not found. Please enter product details manually.'
#         }
        
#         response_serializer = BarcodeScanResponseSerializer(
#             response_data,
#             context={'request': request}
#         )
        
#         return self.success_response(
#             data=response_serializer.data,
#             message="Product not found. Manual entry required.",
#             status_code=200
#         )

class ScanBarcodeView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        user = request.user
        
        # Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        serializer = BarcodeScanRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self.error_response(
                "Invalid barcode format",
                status_code=400,
                data=serializer.errors
            )
        
        barcode = serializer.validated_data['barcode']
        
        # Check if product exists in database
        try:
            shop_product = ShopProduct.objects.get(barcode=barcode)
            
            # ✅ Create ProductScanHistory
            ProductScanHistory.objects.create(
                user=owner,
                shop_product=shop_product,
                barcode=barcode,
                scan_type='barcode'
            )
            
            # ✅ FIX: Check if already in user's inventory
            user_product, created = UserProduct.objects.get_or_create(
                user=owner,
                product=shop_product,
                defaults={
                    'current_weight_grams': Decimal('0.00'),  # User adds weight later
                    'user_price': shop_product.market_price,
                    'is_available': True  # Not available until weight added
                }
            )
            
            response_data = {
                'found_in_db': True,
                'found_in_api': False,
                'manual_entry_required': shop_product.market_price == Decimal('0.00'),
                'product': shop_product,
                'user_product_id': user_product.id,  # ✅ Include this
                'message': 'Product found. Add weight to complete.' if created else 'Product already in inventory.'
            }
            
            response_serializer = BarcodeScanResponseSerializer(
                response_data,
                context={'request': request}
            )
            
            return self.success_response(
                data=response_serializer.data,
                message="Product scanned successfully",
                status_code=200
            )
            
        except ShopProduct.DoesNotExist:
            from .barcode_utils import barcode_api
            
            api_result = barcode_api.lookup_barcode(barcode)
            
            if api_result:
                # Create ShopProduct from API
                shop_product = ShopProduct.objects.create(
                    name=api_result['name'],
                    description=api_result.get('description', ''),
                    barcode=barcode,
                    market_price=Decimal('0.00'),
                    api_data=api_result.get('raw_data')
                )
                
                # Create scan history
                ProductScanHistory.objects.create(
                    user=owner,
                    shop_product=shop_product,
                    barcode=barcode,
                    scan_type='barcode'
                )
                
                # ✅ FIX: Create UserProduct immediately with 0 weight
                user_product = UserProduct.objects.create(
                    user=owner,
                    product=shop_product,
                    current_weight_grams=Decimal('0.00'),
                    user_price=Decimal('0.00'),
                    is_available=True  # Not available until weight/price added
                )
                
                # Check price/weight from API
                raw_data = api_result.get('raw_data', {})
                stores = raw_data.get('Stores', [])
                has_price = any(store.get('price', '').strip() for store in stores)
                has_weight = bool(api_result.get('weight', '').strip())
                
                # response_data = {
                #     'found_in_db': False,
                #     'found_in_api': True,
                #     'manual_entry_required': not (has_price and has_weight),
                #     'product': {
                #         'id': shop_product.id,
                #         'user_product_id': user_product.id,  # ✅ Include this
                #         'name': api_result['name'],
                #         'description': api_result.get('description', ''),
                #         'barcode': barcode,
                #         'brand': api_result.get('brand', ''),
                #         'category': api_result.get('category', ''),
                #         'image_url': api_result.get('image_url', ''),
                #         'weight': api_result.get('weight', ''),
                #         'stores': raw_data.get('Stores', []),
                #         'needs_price': not has_price,
                #         'needs_weight': not has_weight
                #     },
                response_data = {
                    'found_in_db': False,
                    'found_in_api': True,
                    'manual_entry_required': not (has_price and has_weight),
                    'product': {
                        'id': shop_product.id,
                        'user_product_id': user_product.id,
                        'name': api_result['name'],
                        'description': api_result.get('description', ''),
                        'barcode': barcode,
                        'brand': api_result.get('brand', ''),
                        'manufacturer': api_result.get('manufacturer', ''),  # ✅ ADD
                        'category': api_result.get('category', ''),
                        'image_url': api_result.get('image_url', ''),
                        'weight': api_result.get('weight', ''),
                        'model': api_result.get('model', ''),  # ✅ ADD
                        'asin': api_result.get('asin', ''),  # ✅ ADD
                        'mpn': api_result.get('mpn', ''),  # ✅ ADD
                        'upc': api_result.get('upc', ''),  # ✅ ADD
                        'ean': api_result.get('ean', ''),  # ✅ ADD
                        'color': api_result.get('color', ''),  # ✅ ADD
                        'size': api_result.get('size', ''),  # ✅ ADD
                        'stores': raw_data.get('Stores', []),
                        'needs_price': not has_price,
                        'needs_weight': not has_weight
                    },
                    'message': 'Product found. Add weight/price to activate.'
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
            
            return self.error_response(
                "Product not found in database or API",
                status_code=404
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

    # ✅ Update ShopProduct description if provided
        if 'description' in validated_data:
            shop_product.description = validated_data['description']
            shop_product.save(update_fields=['description', 'updated_at'])
            updated_fields['description'] = validated_data['description']
            
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

#====================================================================================================
#cart related view
# Add this view to mixapp/views.py

class AddToCartView(StandardResponseMixin, APIView):
    """Add product to shopping cart"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """
        Add product to cart
        
        Request body:
        - shop_product_id: Product ID
        - quantity: Quantity to add
        """
        user = request.user
        shop_product_id = request.data.get('shop_product_id')
        quantity = request.data.get('quantity', 1)
        
        # Validate product
        try:
            shop_product = ShopProduct.objects.select_related('retailer').get(id=shop_product_id)
        except ShopProduct.DoesNotExist:
            return self.error_response("Product not found", status_code=404)
        
        # Check stock
        if shop_product.quantity < quantity:
            return self.error_response(
                f"Insufficient stock. Available: {shop_product.quantity}",
                status_code=400
            )
        
        # Add to cart or update quantity
        cart_item, created = ShoppingCart.objects.get_or_create(
            user=user,
            shop_product=shop_product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        
        return self.success_response(
            data={
                'cart_item_id': cart_item.id,
                'product_name': shop_product.name,
                'quantity': cart_item.quantity,
                'unit_price': str(shop_product.market_price),
                'total_price': str(cart_item.total_price)
            },
            message="Product added to cart",
            status_code=201
        )


class ViewCartView(StandardResponseMixin, APIView):
    """View shopping cart"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get cart items with total"""
        user = request.user
        
        cart_items = ShoppingCart.objects.filter(user=user).select_related(
            'shop_product__retailer'
        )
        
        if not cart_items.exists():
            return self.success_response(
                data={
                    'cart_items': [],
                    'total_items': 0,
                    'total_price': '0.00'
                },
                message="Cart is empty",
                status_code=200
            )
        
        # Prepare cart data
        items_data = []
        total_price = Decimal('0.00')
        
        for item in cart_items:
            item_total = item.total_price
            total_price += item_total
            
            items_data.append({
                'cart_item_id': item.id,
                'product_id': item.shop_product.id,
                'product_name': item.shop_product.name,
                'retailer_name': item.shop_product.retailer.business_name if item.shop_product.retailer else 'Unknown',
                'quantity': item.quantity,
                'unit_price': str(item.shop_product.market_price),
                'total_price': str(item_total),
                'image_url': request.build_absolute_uri(item.shop_product.image.url) if item.shop_product.image else None
            })
        
        return self.success_response(
            data={
                'cart_items': items_data,
                'total_items': cart_items.count(),
                'total_price': str(total_price)
            },
            message="Cart retrieved successfully",
            status_code=200
        )


class RemoveFromCartView(StandardResponseMixin, APIView):
    """Remove product from cart"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def delete(self, request, cart_item_id):
        """Remove cart item"""
        user = request.user
        
        try:
            cart_item = ShoppingCart.objects.get(id=cart_item_id, user=user)
            product_name = cart_item.shop_product.name
            cart_item.delete()
            
            return self.success_response(
                message=f"{product_name} removed from cart",
                status_code=200
            )
        except ShoppingCart.DoesNotExist:
            return self.error_response("Cart item not found", status_code=404)


class UpdateCartItemView(StandardResponseMixin, APIView):
    """Update cart item quantity"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def patch(self, request, cart_item_id):
        """Update quantity"""
        user = request.user
        quantity = request.data.get('quantity')
        
        if not quantity or quantity < 1:
            return self.error_response("Quantity must be at least 1", status_code=400)
        
        try:
            cart_item = ShoppingCart.objects.select_related('shop_product').get(
                id=cart_item_id,
                user=user
            )
            
            # Check stock
            if cart_item.shop_product.quantity < quantity:
                return self.error_response(
                    f"Insufficient stock. Available: {cart_item.shop_product.quantity}",
                    status_code=400
                )
            
            cart_item.quantity = quantity
            cart_item.save()
            
            return self.success_response(
                data={
                    'cart_item_id': cart_item.id,
                    'quantity': cart_item.quantity,
                    'total_price': str(cart_item.total_price)
                },
                message="Cart updated",
                status_code=200
            )
        except ShoppingCart.DoesNotExist:
            return self.error_response("Cart item not found", status_code=404)



#==========================================================
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Expense
from .serializers import ExpenseSerializer

class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] 

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)




#======================================================

class RetailerProductsListView(StandardResponseMixin, APIView):
    """
    GET: All products uploaded by retailers (for purchasing)
    Available to all authenticated users
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all retailer products (shop products)"""
        
        # ✅ Filter: Only show products from approved retailers with Stripe connected
        queryset = ShopProduct.objects.filter(
            retailer__isnull=False,
            retailer__is_approved=True,
            retailer__stripe_connected=True
        ).select_related('retailer').order_by('-created_at')
        
        # ✅ Filter by stock status
        stock_status = request.query_params.get('stock_status')
        if stock_status in ['in_stock', 'out_of_stock', 'low_stock']:
            queryset = queryset.filter(stock_status=stock_status)
        
        # ✅ Search by name
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # ✅ Filter by retailer
        retailer_id = request.query_params.get('retailer_id')
        if retailer_id:
            queryset = queryset.filter(retailer_id=retailer_id)
        
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
            message="Retailer products retrieved",
            status_code=200
        )


class UserInventoryProductsView(StandardResponseMixin, APIView):
    """
    GET: User's own inventory (scanned + manual entry products)
    Shows UserProduct records for this user
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's inventory products"""
        user = request.user
        
        # ✅ Get correct owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # ✅ Get user products
        queryset = UserProduct.objects.filter(
            user=owner
        ).select_related('product').order_by('-scanned_at')
        
        # ✅ Filter by availability
        is_available = request.query_params.get('is_available')
        if is_available is not None:
            queryset = queryset.filter(is_available=is_available.lower() == 'true')
        
        # ✅ Search by product name
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(product__name__icontains=search)
        
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
            message="User inventory retrieved",
            status_code=200
        )



#============================================================================================================================


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import FinancialOverviewSerializer

class FinancialOverviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/mix/financial-overview/?months=12
        GET /api/mix/financial-overview/?month=1&year=2026  (January 2026)
        GET /api/mix/financial-overview/?month=2&year=2026  (February 2026)
        
        Returns monthly profit from mixes and costs from product checkout
        
        Query params:
        - months: number of months to retrieve (default: 12, max: 24) - for range
        - month: specific month (1-12) - for single month
        - year: specific year (required if month is provided)
        
        Response:
        {
            "success": true,
            "period": "February 2026" or "Last 12 months",
            "overview": [
                {
                    "month": "February",
                    "year": 2026,
                    "total_profit": 1500.00,
                    "total_cost": 800.00,
                    "net_amount": 700.00
                }
            ]
        }
        """
        '''
        try:
            months = int(request.query_params.get('months', 12))
            
            if months > 24:
                months = 24
            if months < 1:
                months = 1
            
            serializer = FinancialOverviewSerializer()
            overview_data = serializer.get_overview_data(request.user, months)
            
            return Response({
                'success': True,
                'period': f'Last {months} months',
                'overview': overview_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        '''


        try:
            # Check if specific month filter is requested
            month = request.query_params.get('month')
            year = request.query_params.get('year')
            
            # serializer = FinancialOverviewSerializer()
            # ✅ FIX: Import the helper functions
            from .serializers import get_single_month_overview, get_multiple_months_overview
            
            if month and year:
                # ✅ Filter by specific month
                try:
                    month_num = int(month)
                    year_num = int(year)
                    
                    if month_num < 1 or month_num > 12:
                        return Response({
                            'success': False,
                            'error': 'Month must be between 1 and 12'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # overview_data = serializer.get_single_month_data(
                    #     request.user, 
                    #     month_num, 
                    #     year_num
                    # )
                    overview_data = get_single_month_overview(request.user, month_num, year_num)
                    period = f"{overview_data[0]['month']} {year_num}" if overview_data else f"Month {month_num}, {year_num}"
                    
                except ValueError:
                    return Response({
                        'success': False,
                        'error': 'Invalid month or year format'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # ✅ Get range of months
                months = int(request.query_params.get('months', 12))
                
                if months > 24:
                    months = 24
                if months < 1:
                    months = 1
                
                #overview_data = serializer.get_overview_data(request.user, months)
                overview_data = get_multiple_months_overview(request.user, months)
                period = f'Last {months} months'
            
            return Response({
                'success': True,
                'period': period,
                'overview': overview_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




# ============================================================
# Earning Overview Chart
# ============================================================

class EarningOverviewView(APIView):
    """
    GET /api/mix/earning-overview/
    GET /api/mix/earning-overview/?year=2025
    
    ✅ Access: Owner & Self-Employed ONLY
    ❌ Staff: No access (staff payment handled by owner)
    
    Returns:
    - income_by_mix_creation: Monthly income from mixes
    - expense_by_product_purchase: Monthly product purchase costs
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # ✅ Block staff users
        if user.role == 'staff':
            return Response({
                'success': False,
                'message': 'Access denied. Only Owner or Self-Employed can view earning overview.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # ✅ Only owner and self_employed allowed
        if user.role not in ['owner', 'self_employed']:
            return Response({
                'success': False,
                'message': 'Access denied.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # ✅ Get year from query params (default: current year)
        year = request.query_params.get('year')
        try:
            year = int(year) if year else timezone.now().year
        except ValueError:
            return Response({
                'success': False,
                'message': 'Invalid year format.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from .serializers import get_earning_overview
        
        data = get_earning_overview(user, year)
        
        return Response({
            'success': True,
            'year': year,
            'data': data
        }, status=status.HTTP_200_OK)
    
#===================================================================================================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from calendar import month_name

from mixapp.models import Mix
from paymentapp.models import Payment
from .serializers import Accountsdepartment, MonthlyBreakdownSerializer


class StandardResponseMixin:
    def success_response(self, data=None, message="Success", status_code=200):
        response = {"success": True, "statusCode": status_code, "message": message}
        if data is not None:
            response["data"] = data
        return Response(response, status=status_code)

    def error_response(self, message, status_code=400, data=None):
        response = {"success": False, "statusCode": status_code, "message": message}
        if data is not None:
            response["data"] = data
        return Response(response, status=status_code)


class AccountsDashboardOverviewView(StandardResponseMixin, APIView):
    """
    Dashboard overview for owner and self_employed roles only.

    Query Params:
    - filter_type : 'monthly' (default) or 'yearly'
    - year        : e.g. 2025  (default = current year)
    - month       : e.g. 3     (required only when filter_type=monthly, default = current month)
    """
    permission_classes = [IsAuthenticated]

    ALLOWED_ROLES = ['owner', 'self_employed']

    def get(self, request):
        user = request.user

        # ✅ Role check
        if not hasattr(user, 'role') or user.role not in self.ALLOWED_ROLES:
            return self.error_response(
                "Access denied. Only owner and self_employed can view dashboard.",
                status_code=403
            )

        # ✅ Parse query params
        filter_type = request.query_params.get('filter_type', 'monthly').lower()
        now = timezone.now()

        try:
            year = int(request.query_params.get('year', now.year))
        except ValueError:
            return self.error_response("Invalid year format.", status_code=400)

        try:
            month = int(request.query_params.get('month', now.month))
        except ValueError:
            return self.error_response("Invalid month format.", status_code=400)

        if filter_type not in ['monthly', 'yearly']:
            return self.error_response(
                "filter_type must be 'monthly' or 'yearly'.",
                status_code=400
            )

        if filter_type == 'monthly':
            # ✅ Monthly: single month income & expense
            income = self._get_monthly_income(user, year, month)
            expense = self._get_monthly_expense(user, year, month)

            dashboard_data = self._build_user_data(
                user=user,
                request=request,
                income=income,
                expense=expense,
                filter_type=filter_type,
                year=year,
                month=month
            )

            return self.success_response(
                data=dashboard_data,
                message="Monthly dashboard retrieved successfully."
            )

        else:
            # ✅ Yearly: total + month-by-month breakdown
            yearly_income = Decimal('0.00')
            yearly_expense = Decimal('0.00')
            breakdown = []

            for m in range(1, 13):
                m_income = self._get_monthly_income(user, year, m)
                m_expense = self._get_monthly_expense(user, year, m)
                yearly_income += m_income
                yearly_expense += m_expense

                breakdown.append({
                    "month": m,
                    "month_name": month_name[m],
                    "income": m_income,
                    "expense": m_expense,
                    "net_profit": m_income - m_expense,
                })

            dashboard_data = self._build_user_data(
                user=user,
                request=request,
                income=yearly_income,
                expense=yearly_expense,
                filter_type=filter_type,
                year=year,
                month=None
            )

            # ✅ Attach monthly breakdown for yearly filter
            dashboard_data['monthly_breakdown'] = MonthlyBreakdownSerializer(
                breakdown, many=True
            ).data

            return self.success_response(
                data=dashboard_data,
                message="Yearly dashboard retrieved successfully."
            )

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    def _get_monthly_income(self, user, year, month):
        """Total profit from mix creation in a given month"""
        result = Mix.objects.filter(
            user=user,
            created_at__year=year,
            created_at__month=month,
        ).aggregate(total=Sum('profit'))
        return result['total'] or Decimal('0.00')

    def _get_monthly_expense(self, user, year, month):
        """Total amount spent on product purchases (completed payments) in a given month"""
        result = Payment.objects.filter(
            user=user,
            status='completed',
            created_at__year=year,
            created_at__month=month,
        ).aggregate(total=Sum('total_amount'))
        return result['total'] or Decimal('0.00')

    def _build_user_data(self, user, request, income, expense, filter_type, year, month):
        """Build the final response dict"""
        profile_image = None
        if hasattr(user, 'profile_image') and user.profile_image:
            try:
                profile_image = request.build_absolute_uri(user.profile_image.url)
            except Exception:
                profile_image = None

        return {
            "user_id": user.id,
            "name": getattr(user, 'name', '') or getattr(user, 'full_name', ''),
            "email": user.email,
            "role": user.role,
            "profile_image": profile_image,
            "total_income": income,
            "total_expense": expense,
            "net_profit": income - expense,
            "filter_type": filter_type,
            "filter_year": year,
            "filter_month": month,
        }

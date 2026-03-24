from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
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
    CustomerDeliveryAddressSerializer, RetailerProfilePublicSetupSerializer,
    RetailerProfileUpdateSerializer, RetailerPublicSerializer,   # ✅ THESE TWO# ✅ ADDed 28th feb
    UpdateRetailerProductSerializer,
    ProductPromoSerializer, BulkPromoSerializer
)
import stripe
from django.conf import settings
from django.shortcuts import render, redirect
stripe.api_key = settings.STRIPE_SECRET_KEY
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.db.models import F, ExpressionWrapper, DecimalField as DjDecimalField, Case, When, Q
from .promo_utils import calculate_promo_price

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
    
    def serializer_error_response(self, errors, status_code=400):
        """Extract first real error from serializer.errors and use as message"""
        message = "Validation failed"
        for field, field_errors in errors.items():
            if field == 'non_field_errors':
                message = field_errors[0] if field_errors else message
                break
            else:
                error_text = field_errors[0] if field_errors else str(field_errors)
                message = f"{field}: {error_text}"
                break
        return self.error_response(message, status_code=status_code, data=errors)


class RetailerProfileSetupView(StandardResponseMixin, APIView):#❌❌❌This view is not currently using 
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
            #====================================================================
            # ✅ removed this line now handle in serializer
            # retailer_profile.is_approved = True
            # retailer_profile.save(update_fields=['is_approved'])
            #====================================================================
            # ✅ Build logo URL# ✅ ADDed 28th feb
            business_logo_url = None
            if retailer_profile.business_logo:
                business_logo_url = request.build_absolute_uri(
                    retailer_profile.business_logo.url
                )
            return self.success_response(
                data={
                    'business_name': retailer_profile.business_name,
                    "business_logo": business_logo_url, # ✅ ADDed 28th feb
                    'delivery_charge': str(retailer_profile.delivery_charge),
                    'free_delivery_threshold': str(retailer_profile.free_delivery_threshold),
                    "api_key": retailer_profile.api_key,  # ✅ ADD THIS LINE
                    'delivery_areas': list(
                        retailer_profile.delivery_areas.values('id', 'area_name')
                    )
                },
                message="Retailer profile setup completed",
                status_code=201
            )
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
    
        '''
        return self.error_response(
            "Profile setup failed",
            status_code=400,
            data=serializer.errors
        )
        '''


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
                'total_count': queryset.count(),
                'api_key': retailer.api_key   # ✅ add here

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
        
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
        '''
        return self.error_response(
            "Failed to create product",
            status_code=400,
            data=serializer.errors
        )
        '''



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
        '''
        
        '''
        # ✅ Allowed fields for update
        # allowed_fields = [
        #     'name', 'description', 'image', 'market_price',
        #     'quantity', 'barcode','vat'
        # ]
        
        # update_data = {
        #     k: v for k, v in request.data.items() if k in allowed_fields
        # }
        
        # serializer = RetailerProductSerializer(
        #     product,
        #     data=update_data,
        #     partial=True,
        #     context={'request': request}
        # )
        serializer = UpdateRetailerProductSerializer(
            product,
            data=request.data,
            partial=True,
        ) 
        if serializer.is_valid():
            product = serializer.save()
            # ✅ Serialize again to get full read fields including image_url
            response_serializer = RetailerProductSerializer(product, context={'request': request})
            return self.success_response(
                #data=serializer.data,
                data=response_serializer.data,  # now includes image_url with full base URL
                message="Product updated successfully",
                status_code=200
            )
        '''
        why response_serializer = RetailerProductSerializer?

        Instead of returning the UpdateRetailerProductSerializer (which only has the raw image field), 
        you now return RetailerProductSerializer with the request context, which uses the get_image_url method
        '''
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
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
    
        # return self.error_response(
        #     "Failed to submit request",
        #     status_code=400,
        #     data=serializer.errors
        # )


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
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
        # return self.error_response(
        #     "Failed to add address",
        #     status_code=400,
        #     data=serializer.errors
        # )


#===================================================new views for retailer 
# ...existing code...

class RetailerOrderListView(StandardResponseMixin, APIView):
    """
    GET: List all orders for retailer
    PATCH: Update order status
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get retailer's orders"""
        user = request.user
        
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)
        
        retailer = user.retailer_profile
        
        # ✅ Get orders
        from paymentapp.models import RetailerOrder
        from paymentapp.serializers import RetailerOrderSerializer
        
        queryset = RetailerOrder.objects.filter(
            retailer=retailer
        ).select_related('payment__user', 'product').order_by('-created_at')
        
        # ✅ Filter by status
        status = request.query_params.get('status')
        if status in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
            queryset = queryset.filter(status=status)
        
        serializer = RetailerOrderSerializer(queryset, many=True)
        
        return self.success_response(
            data={
                'orders': serializer.data,
                'total_count': queryset.count()
            },
            message="Orders retrieved",
            status_code=200
        )


class RetailerOrderDetailView(StandardResponseMixin, APIView):
    """Update order status"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def patch(self, request, order_id):
        """Update order status"""
        user = request.user
        
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)
        
        retailer = user.retailer_profile
        
        from paymentapp.models import RetailerOrder
        
        try:
            order = RetailerOrder.objects.get(id=order_id, retailer=retailer)
        except RetailerOrder.DoesNotExist:
            return self.error_response("Order not found", status_code=404)
        
        new_status = request.data.get('status')
        
        if new_status not in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
            return self.error_response("Invalid status", status_code=400)
        
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        
        from paymentapp.serializers import RetailerOrderSerializer
        serializer = RetailerOrderSerializer(order)
        
        return self.success_response(
            data=serializer.data,
            message="Order status updated",
            status_code=200
        )


class RetailerPaymentListView(StandardResponseMixin, APIView):
    """List all payments received by retailer"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get retailer's payment history"""
        user = request.user
        
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)
        
        retailer = user.retailer_profile
        
        from paymentapp.models import PaymentRetailerSplit
        from paymentapp.serializers import RetailerPaymentSummarySerializer
        
        queryset = PaymentRetailerSplit.objects.filter(
            retailer=retailer
        ).select_related('payment__user').order_by('-created_at')
        
        serializer = RetailerPaymentSummarySerializer(queryset, many=True)
        
        return self.success_response(
            data={
                'payments': serializer.data,
                'total_count': queryset.count(),
                'total_earnings': sum(p.total_transfer_amount for p in queryset)
            },
            message="Payment history retrieved",
            status_code=200
        )

# ...existing code...


#=======================================================================================================================================

#Stripe code for retailer 
# Add to retailerapp/views.py

from .utils import is_stripe_supported_country, is_stripe_onboarding_complete

class RetailerStripeOnboardView(StandardResponseMixin, APIView):
    """Start Stripe Connect onboarding for retailer"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        # if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
        #     return self.error_response("Unauthorized", status_code=403)

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            # For API clients, return JSON error instead of rendering template
            if request.headers.get('Accept') == 'application/json':
                return self.error_response("Unauthorized access", status_code=403)
            return render(request, 'retailer/stripe_error.html', {
                'error': 'Unauthorized access'
            })
        retailer = user.retailer_profile
        
        # if retailer.stripe_connected:
        #     return self.error_response("Already connected to Stripe", status_code=400)

        # if retailer.stripe_connected:
        #     return render(request, 'retailer/stripe_error.html', {
        #         'error': 'Already connected to Stripe'
        #     })

        # ✅ Check if already connected
        '''
        if retailer.stripe_connected:
            return self.success_response(
                message="Stripe account onboarding already completed",
                status_code=200
            )
        '''
        if retailer.stripe_connected:
            if request.headers.get('Accept') == 'application/json':
                return self.success_response(
                    message="Stripe account onboarding already completed",
                    data={
                        "already_connected": True,
                        "stripe_account_id": retailer.stripe_account_id
                    },
                    status_code=200
                )
            return render(request, 'retailer/stripe_success.html', {
                'message': 'Stripe account already connected'
            })
        
        # ✅ Check if account exists and onboarding is complete
        if retailer.stripe_account_id:
            if is_stripe_onboarding_complete(retailer.stripe_account_id):
                retailer.stripe_connected = True
                retailer.stripe_connection_date = timezone.now()
                retailer.save()
                return self.success_response(
                    message="Stripe account onboarding already completed",
                    status_code=200
                )
            
        # ✅ NEW: Get country from request
        country = request.data.get('country', 'GB').upper()
        
        # ✅ NEW: Validate country support
        if not is_stripe_supported_country(country):
            return self.error_response(
                f"{country} is not supported for Stripe Connect",
                status_code=400
            )
        # try:
        #     # Create Stripe Connect account if doesn't exist
        #     if not retailer.stripe_account_id:
        #         account = stripe.Account.create(
        #             type='express',
        #             country='GB',  # Change based on your country
        #             email=user.email,
        #             capabilities={
        #                 'card_payments': {'requested': True},#Stripe requires card_payments capability when requesting transfers for GB accounts.Without this I was getting error:

        #                     # message": "Request req_RlWRpEIEcVpzMu: When requesting the transfers capability for accounts in GB, you must either specify the recipient service agreement, or request the card_payments capability along with transfers. To specify the recipient service agreement, see https://stripe.com/docs/connect/service-agreement-types#choosing-type-with-api. For more information on cross-border transfers, see https://stripe.com/docs/connect/account-capabilities#transfers-cross-border.

        #                 'transfers': {'requested': True}
        #             }
        #         )
        #         retailer.stripe_account_id = account.id
        #         retailer.save(update_fields=['stripe_account_id'])
            
        #     # Create onboarding link
        #     account_link = stripe.AccountLink.create(
        #         account=retailer.stripe_account_id,
        #         type='account_onboarding',
        #         # refresh_url=f"{settings.BASE_URL}/retailer/stripe/refresh",
        #         # return_url=f"{settings.BASE_URL}/retailer/stripe/complete"
        #         refresh_url=f"{settings.BASE_URL}/retailer/stripe/onboard/",
        #         return_url=f"{settings.BASE_URL}/retailer/stripe/complete/?account_id={retailer.stripe_account_id}"
        #     )
        #     # ✅ REDIRECT to Stripe onboarding URL
        #     return redirect(account_link.url)
        #     # return self.success_response(
        #     #     data={
        #     #         'onboarding_url': account_link.url,
        #     #         'account_id': retailer.stripe_account_id
        #     #     },
        #     #     message="Stripe onboarding started",
        #     #     status_code=200
        #     # )
        
        # # except stripe.error.StripeError as e:
        # #     return self.error_response(str(e), status_code=500)
        # except stripe.error.StripeError as e:
        #     return render(request, 'retailer/stripe_error.html', {
        #         'error': str(e)
        #     })
        try:
            # ✅ NEW: Reuse existing account if valid
            if retailer.stripe_account_id:
                try:
                    account = stripe.Account.retrieve(retailer.stripe_account_id)
                    account_id = retailer.stripe_account_id
                except stripe.error.InvalidRequestError:
                    # Account doesn't exist, create new one
                    account = stripe.Account.create(
                        type='express',
                        country=country,
                        email=user.email,
                        capabilities={
                            'card_payments': {'requested': True},
                            'transfers': {'requested': True}
                        }
                    )
                    retailer.stripe_account_id = account.id
                    retailer.save(update_fields=['stripe_account_id'])
                    account_id = account.id
            else:
                # Create new account
                account = stripe.Account.create(
                    type='express',
                    country=country,
                    email=user.email,
                    capabilities={
                        'card_payments': {'requested': True},
                        #Stripe requires card_payments capability when requesting transfers for GB accounts.Without this I was getting error:

        #                     # message": "Request req_RlWRpEIEcVpzMu: When requesting the transfers capability for accounts in GB, you must either specify the recipient service agreement, or request the card_payments capability along with transfers. To specify the recipient service agreement, see https://stripe.com/docs/connect/service-agreement-types#choosing-type-with-api. For more information on cross-border transfers, see https://stripe.com/docs/connect/account-capabilities#transfers-cross-border.
                        'transfers': {'requested': True}
                    }
                )
                retailer.stripe_account_id = account.id
                retailer.save(update_fields=['stripe_account_id'])
                account_id = account.id
            
            # ✅ IMPROVED: Better redirect URLs with status
            account_link = stripe.AccountLink.create(
                account=account_id,
                type='account_onboarding',
                refresh_url=f"{settings.BASE_URL}/retailer/stripe/onboard-complete/?onboard=error&account_id={account_id}",
                return_url=f"{settings.BASE_URL}/retailer/stripe/onboard-complete/?onboard=success&account_id={account_id}"
            )
            '''
                        return redirect(account_link.url)
        
        except stripe.error.StripeError as e:
            return render(request, 'retailer/stripe_error.html', {
                'error': str(e)
            })
            '''
            # ✅ For browser requests: Redirect
            if request.method == "GET":
                return redirect(account_link.url)

            # ✅ For API requests: Return JSON with URL
            return Response({
                "onboarding_url": account_link.url,
                "account_id": account_id,
                "message": "Open onboarding_url in browser to complete setup"
            })

        except stripe.error.StripeError as e:
                return Response({
                    "error": str(e)
                }, status=500)

# class RetailerStripeCompleteView(StandardResponseMixin, APIView):
#     """Handle Stripe onboarding completion"""
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request):
#         user = request.user
#         retailer = user.retailer_profile
        
#         try:
#             account = stripe.Account.retrieve(retailer.stripe_account_id)
            
#             if account.charges_enabled and account.details_submitted:
#                 retailer.stripe_connected = True
#                 retailer.stripe_connection_date = timezone.now()
#                 retailer.save()
                
#                 return self.success_response(
#                     message="Stripe account connected successfully",
#                     status_code=200
#                 )
#             else:
#                 return self.error_response(
#                     "Stripe onboarding incomplete",
#                     status_code=400
#                 )
        
#         except stripe.error.StripeError as e:
#             return self.error_response(str(e), status_code=500)

# ...existing code...

'''
class RetailerStripeCompleteView(StandardResponseMixin, APIView):
    """Handle Stripe onboarding completion with status"""
    permission_classes = [AllowAny]  # Changed to AllowAny for Stripe redirects
    
    def get(self, request):
        account_id = request.GET.get('account_id')
        onboard_status = request.GET.get('onboard')
        
        if not account_id:
            return redirect(f"{settings.BASE_URL}/retailer/dashboard/?onboard=error")
        
        try:
            from .models import RetailerProfile
            retailer = RetailerProfile.objects.get(stripe_account_id=account_id)
            
            # ✅ Always verify—ignore URL params
            if is_stripe_onboarding_complete(account_id):
                if not retailer.stripe_connected:
                    retailer.stripe_connected = True
                    retailer.stripe_connection_date = timezone.now()
                    retailer.save()
                return redirect(f"{settings.BASE_URL}/retailer/dashboard/?onboard=success")
            else:
                # Incomplete onboarding
                return redirect(f"{settings.BASE_URL}/retailer/dashboard/?onboard=incomplete&account_id={account_id}")
        
        except RetailerProfile.DoesNotExist:
            return redirect(f"{settings.BASE_URL}/retailer/dashboard/?onboard=error")
        except Exception as e:
            return redirect(f"{settings.BASE_URL}/retailer/dashboard/?onboard=error")
'''
class RetailerStripeCompleteView(APIView):
    """Handle Stripe onboarding completion with HTML pages"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        account_id = request.GET.get('account_id')
        onboard_status = request.GET.get('onboard')
        
        if not account_id:
            return render(request, 'retailer/stripe_error.html', {
                'error': 'Missing account ID'
            })
        
        try:
            from .models import RetailerProfile
            retailer = RetailerProfile.objects.get(stripe_account_id=account_id)
            
            # ✅ Verify onboarding completion
            if is_stripe_onboarding_complete(account_id):
                if not retailer.stripe_connected:
                    retailer.stripe_connected = True
                    retailer.stripe_connection_date = timezone.now()
                    retailer.save()
                
                # ✅ Render SUCCESS page
                return render(request, 'retailer/stripe_success.html', {
                    'business_name': retailer.business_name,
                    'account_id': account_id
                })
            else:
                # ✅ Render INCOMPLETE page
                return render(request, 'retailer/stripe_incomplete.html', {
                    'retry_url': f"{settings.BASE_URL}/retailer/stripe/onboard/",
                    'account_id': account_id
                })
        
        except RetailerProfile.DoesNotExist:
            return render(request, 'retailer/stripe_error.html', {
                'error': 'Retailer account not found'
            })
        except Exception as e:
            return render(request, 'retailer/stripe_error.html', {
                'error': str(e)
            })


class RetailerStripeStatusView(StandardResponseMixin, APIView):
    """Check retailer's Stripe connection status"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)
        
        retailer = user.retailer_profile
        
        return self.success_response(
            data={
                "stripe_connected": retailer.stripe_connected,
                "stripe_connection_status": "connected" if retailer.stripe_connected else "not_connected",
                "stripe_account_id": retailer.stripe_account_id,
                "connection_date": retailer.stripe_connection_date
            },
            message="Stripe status retrieved",
            status_code=200
        )


@csrf_exempt
def retailer_dashboard_view(request):
    """Render dashboard with Stripe onboarding status"""
    account_id = request.GET.get("account_id")
    
    # Case 1: Stripe redirect -> use account_id
    if account_id:
        try:
            from .models import RetailerProfile
            retailer = RetailerProfile.objects.get(stripe_account_id=account_id)
        except RetailerProfile.DoesNotExist:
            return render(request, "retailer/dashboard.html", {
                "onboard_status": "error",
                "account_id": None,
            })
    else:
        # Case 2: Normal dashboard access -> use logged in user
        if request.user.is_authenticated and hasattr(request.user, 'retailer_profile'):
            retailer = request.user.retailer_profile
        else:
            retailer = None
    
    onboard_status = request.GET.get("onboard")
    
    context = {
        "onboard_status": onboard_status,
        "account_id": getattr(retailer, "stripe_account_id", None),
        "stripe_connected": getattr(retailer, "stripe_connected", False),
    }
    return render(request, 'retailer/dashboard.html', context)


#========================================================================================================\
# Latest retailer profiel setup view which is using now

class RetailerProfilePublicSetupView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    @transaction.atomic
    def post(self, request):
        serializer = RetailerProfilePublicSetupSerializer(
            data=request.data
        )

        if serializer.is_valid():
            retailer_profile = serializer.save()
            # ✅ Build logo URL
            business_logo_url = None
            if retailer_profile.business_logo:
                business_logo_url = f"{settings.BASE_URL}{retailer_profile.business_logo.url}"
                # business_logo_url = request.build_absolute_uri(
                #     retailer_profile.business_logo.url
                # )
            return self.success_response(
                data={
                    "email":retailer_profile.user.email,
                    "business_name": retailer_profile.business_name,
                    "business_logo": business_logo_url,      # ✅ ADDED
                    "delivery_charge": str(retailer_profile.delivery_charge),
                    "free_delivery_threshold": str(retailer_profile.free_delivery_threshold),
                    "api_key": retailer_profile.api_key,
                    "delivery_areas": list(
                        retailer_profile.delivery_areas.values("id", "area_name")
                    )
                },
                message="Retailer profile setup completed",
                status_code=201
            )
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
        # return self.error_response(
        #     "Profile setup failed",
        #     status_code=400,
        #     data=serializer.errors
        # )
    def patch(self, request):
        user = request.user
        try:
            retailer = user.retailer_profile
        except RetailerProfile.DoesNotExist:
            return self.error_response("Retailer profile not found", status_code=404)

        serializer = RetailerProfileUpdateSerializer(
            retailer,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return self.success_response(
                data=serializer.data,
                message="Profile updated successfully",
                status_code=200
            )
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
        #return self.error_response(serializer.errors, status_code=400)
# ...existing code...

class RetailerMyProfileView(StandardResponseMixin, APIView):
    """
    GET: Retailer sees own profile + all products (token based)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)

        retailer = user.retailer_profile

        retailer_serializer = RetailerPublicSerializer(
            retailer, context={'request': request}
        )

        products = ShopProduct.objects.filter(retailer=retailer).order_by('-created_at')

        product_serializer = RetailerProductSerializer(
            products, many=True, context={'request': request}
        )

        return self.success_response(
            data={
                'retailer': retailer_serializer.data,
                'products': product_serializer.data,
                'total_products': products.count()
            },
            message="Retailer details retrieved successfully",
            status_code=200
        )


#===============================================================================\
# ✅ ADDed 28th feb

class RetailerListView(StandardResponseMixin, APIView):
    """
    App store - list all approved retailers with logo, name, delivery info.
    Accessible by all authenticated users (owner, staff, self-employed).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        retailers = RetailerProfile.objects.filter(
            is_approved=True,
            stripe_connected=True  # ✅ ADD THIS
        ).prefetch_related('delivery_areas')
        #  # ✅ ADD: Only show retailer-uploaded products (exclude scanned/manual entry products) + etailer who connected with stripe 
        # queryset = ShopProduct.objects.select_related('retailer').filter(
        #     retailer__isnull=False,
        #     retailer__is_approved=True,
        #     retailer__stripe_connected=True  # ✅ ADD THIS
        # ).order_by('-average_rating', 'name')
        serializer = RetailerPublicSerializer(
            retailers, many=True, context={'request': request}
        )
        return self.success_response(
            data={
                'retailers': serializer.data,
                'total_count': retailers.count()
            },
            message="Retailers retrieved successfully",
            status_code=200
        )


class RetailerPublicDetailView(StandardResponseMixin, APIView):
    """
    App - click on a retailer → see detail info + all his in-stock products.
    Accessible by all authenticated users.
    Also used by retailer dashboard (retailer_id = own id).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, retailer_id):
        try:
            retailer = RetailerProfile.objects.prefetch_related(
                'delivery_areas'
            ).get(id=retailer_id)
        except RetailerProfile.DoesNotExist:
            return self.error_response("Retailer not found", status_code=404)

        # ✅ Retailer info
        retailer_serializer = RetailerPublicSerializer(
            retailer, context={'request': request}
        )

        # ✅ Products with quantity > 0 only
        # If request user IS the retailer → show all his products (dashboard)
        # If request user is app user → show only in-stock (quantity > 0)
        is_own_dashboard = (
            hasattr(request.user, 'retailer_profile') and
            request.user.retailer_profile.id == retailer_id
        )

        if is_own_dashboard:
            products = ShopProduct.objects.filter(retailer=retailer)
        else:
            products = ShopProduct.objects.filter(retailer=retailer, quantity__gt=0)

        product_serializer = RetailerProductSerializer(
            products, many=True, context={'request': request}
        )

        return self.success_response(
            data={
                'retailer': retailer_serializer.data,
                'products': product_serializer.data,
                'total_products': products.count()
            },
            message="Retailer details retrieved successfully",
            status_code=200
        )

#======================================================================================================\


# ...existing code...

from django.db.models import F, ExpressionWrapper, DecimalField as DjDecimalField
from .serializers import BulkDiscountSerializer
# ...existing code...

class RetailerBulkDiscountView(StandardResponseMixin, APIView):
    """
    Apply bulk discount to all retailer products.
    discount_type: 'percentage' or 'amount'
    discount_value: e.g. 2 (means 2% or $2)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)
        
        retailer = user.retailer_profile
        from .models import DiscountLog
        logs = DiscountLog.objects.filter(retailer=retailer)[:10]  # last 10
        data = [
            {
                "discount_type": log.discount_type,
                "discount_value": str(log.discount_value),
                "products_affected": log.products_affected,
                "products_skipped": log.products_skipped,
                "applied_at": log.created_at,
            }
            for log in logs
        ]
        return self.success_response(data={"history": data}, message="Discount history", status_code=200)
    
    @transaction.atomic
    def post(self, request):
        user = request.user

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)

        serializer = BulkDiscountSerializer(data=request.data)
        if not serializer.is_valid():

            # --- NEW LOGIC START ---
            # Extract all error messages into a single list
            errors = []
            error_data = serializer.errors
            
            # Check for non-field errors (like the 100% check)
            if 'non_field_errors' in error_data:
                errors.extend(error_data['non_field_errors'])
            
            # Check for field-specific errors (like negative values)
            for field, field_errors in error_data.items():
                if field != 'non_field_errors':
                    # field_errors is usually a list of strings
                    errors.extend(field_errors)
            
            # Join them into one clear message
            full_message = "Invalid data: " + "; ".join(errors)
            # --- NEW LOGIC END ---
            
            return self.error_response(
                full_message,
                status_code=400,
                data=serializer.errors
            )

        retailer = user.retailer_profile
        discount_type = serializer.validated_data['discount_type']
        discount_value = serializer.validated_data['discount_value']

        # Get all retailer products
        #products = ShopProduct.objects.filter(retailer=retailer)
        product_ids = serializer.validated_data.get('product_ids', [])

        products = ShopProduct.objects.filter(retailer=retailer)

        if product_ids:
            products = products.filter(id__in=product_ids)
        total_products = products.count()

        affected_count = 0
        skipped_count = 0

        if total_products == 0:
            return self.error_response("No products found", status_code=404)
        
        scope = f"{total_products} specific products" if product_ids else f"all {total_products} products"
        if discount_type == 'percentage':
            # Formula: new_price = market_price - (market_price * discount_value / 100)
            # Only update products where new price will be > 0
            # market_price * (1 - discount_value/100) > 0 → always true if discount < 100%
            # But we ensure minimum price of 0.01
            
            # Products where reduced price >= 0.01
            multiplier = Decimal('1') - (discount_value / Decimal('100'))
            
            # Filter: only update products where market_price * multiplier >= 0.01
            '''
            eligible = products.filter(
                Q(discounted_market_price__isnull=False, discounted_market_price__gte=Decimal('0.01') / multiplier) |
                Q(discounted_market_price__isnull=True, market_price__gte=Decimal('0.01') / multiplier)
            )
            '''
            eligible=products.filter(market_price__gte=Decimal('0.01') / multiplier)#because market_price is always the base now.
            affected_count = eligible.count()
            skipped_count = total_products - eligible.count()
            '''
            if affected_count > 0:
                eligible.update(
                    market_price=ExpressionWrapper(
                        F('market_price') * multiplier,
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    )
                )
            if affected_count > 0:
                eligible.update(
                    # ✅ market_price untouched, only discounted_price changes
                    discounted_market_price=ExpressionWrapper(
                        F('base_price') * multiplier,
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    ),
                    discount_percentage=discount_value,
                    discount_amount=Decimal('0.00')
                )
            '''

            '''
            if affected_count > 0:
                eligible.update(
                    discounted_market_price=ExpressionWrapper(
                        # ✅ Use discounted_market_price if exists, else market_price
                        Case(
                            When(discounted_market_price__isnull=False,
                                 then=F('discounted_market_price') * multiplier),
                            default=F('market_price') * multiplier,
                            output_field=DjDecimalField(max_digits=10, decimal_places=2)
                        ),
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    ),
                    discount_percentage=discount_value,
                    discount_amount=Decimal('0.00')
                )
            '''
        if affected_count > 0:
            eligible.update(
                discounted_market_price=ExpressionWrapper(
                    F('market_price') * multiplier,
                    output_field=DjDecimalField(max_digits=10, decimal_places=2)
                ),
                discount_percentage=discount_value,
                discount_amount=Decimal('0.00')
            )
        else:  # amount
            # Only update products where market_price > discount_value (to keep price >= 0.01)
            
            eligible = products.filter(market_price__gt=discount_value)
            '''
            eligible = products.filter(
                Q(discounted_market_price__isnull=False, discounted_market_price__gt=discount_value) |
                Q(discounted_market_price__isnull=True, market_price__gt=discount_value)
            )
            '''
           
            affected_count = eligible.count()
            skipped_count = total_products - eligible.count()
            '''
            if affected_count > 0:
                eligible.update(
                    market_price=ExpressionWrapper(
                        F('market_price') - discount_value,
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    )
                )
            if affected_count > 0:
                eligible.update(
                    # ✅ market_price untouched, only discounted_price changes
                    discounted_market_price=ExpressionWrapper(
                        F('base_price') - discount_value,
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    ),
                    discount_amount=discount_value,
                    discount_percentage=Decimal('0.00')
                )
            '''

            if affected_count > 0:
                '''
                eligible.update(
                    discounted_market_price=ExpressionWrapper(
                        # ✅ Use discounted_market_price if exists, else market_price
                        Case(
                            When(discounted_market_price__isnull=False,
                                 then=F('discounted_market_price') - discount_value),
                            default=F('market_price') - discount_value,
                            output_field=DjDecimalField(max_digits=10, decimal_places=2)
                        ),
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    ),
                    discount_amount=discount_value,
                    discount_percentage=Decimal('0.00')
                )
                '''
                eligible.update(
                    discounted_market_price=ExpressionWrapper(
                        F('market_price') - discount_value,
                        output_field=DjDecimalField(max_digits=10, decimal_places=2)
                    ),
                    discount_amount=discount_value,
                    discount_percentage=Decimal('0.00')
                )
        # ✅ Save audit log
        from .models import DiscountLog
        DiscountLog.objects.create(
            retailer=retailer,
            discount_type=discount_type,
            discount_value=discount_value,
            products_affected=affected_count,
            products_skipped=skipped_count
        )
        # Determine the skip reason only if there are skipped products
        skip_reason = "Skipped products would have price ≤ 0 after discount" if skipped_count > 0 else None

        # Customize the message based on whether any products were actually affected
        if affected_count == 0 and skipped_count > 0:
            message = f"No products updated. {skipped_count} products skipped because their price would be ≤ 0 after discount."
        elif affected_count == 0 and skipped_count == 0:
            message = "No products matched the criteria for discounting."
        elif affected_count !=0 and skipped_count == 0:
            message = f"Discount applied successfully to {affected_count} products."
        else:
            message = f"Discount applied successfully to {affected_count} products. {skipped_count} products skipped because their price would be ≤ 0 after discount."

        return self.success_response(
            data={
                "discount_type": discount_type,
                "discount_value": str(discount_value),
                "total_products": total_products,
                "products_affected": affected_count,
                "products_skipped": skipped_count,
                # "skip_reason": "Skipped products would have price ≤ 0 after discount" if skipped_count > 0 else None
                "skip_reason": skip_reason  # This will now correctly show the reason if skipped_count > 0
            },
            # message=f"Discount applied successfully to {affected_count} products",
            message=message,
            status_code=200
        )

    @transaction.atomic
    def delete(self, request):
        user = request.user

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)

        retailer = user.retailer_profile

        '''
        products = ShopProduct.objects.filter(
            retailer=retailer,
            discounted_market_price__isnull=False
        )
        '''
        product_ids = request.data.get('product_ids', [])

        products = ShopProduct.objects.filter(
            retailer=retailer,
            discounted_market_price__isnull=False
        )

        if product_ids:
            products = products.filter(id__in=product_ids)

        total_products = products.count()

        if total_products == 0:
            return self.error_response("No discounted products found", status_code=404)

        products.update(
            discounted_market_price=None,
            discount_percentage=Decimal('0.00'),
            discount_amount=Decimal('0.00')
        )

        return self.success_response(
            data={
                "products_updated": total_products
            },
            message=f"Bulk discount removed from {total_products} products",
            status_code=200
        )


class RetailerSingleProductDiscountView(StandardResponseMixin, APIView):
    """Apply discount to a specific product"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, product_id):
        user = request.user

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)

        try:
            product = ShopProduct.objects.get(id=product_id, retailer=user.retailer_profile)
        except ShopProduct.DoesNotExist:
            return self.error_response("Product not found", status_code=404)

        serializer = BulkDiscountSerializer(data=request.data)
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)  # ✅ CHANGED

        discount_type = serializer.validated_data['discount_type']
        discount_value = serializer.validated_data['discount_value']

        # ✅ Use discounted_market_price as base if it exists, else use market_price
        # base_price = product.discounted_market_price if product.discounted_market_price else product.market_price
        base_price = product.market_price

        if discount_type == 'percentage':
            multiplier = Decimal('1') - (discount_value / Decimal('100'))
            # new_price = product.market_price * multiplier
            new_price = base_price * multiplier
            if new_price < Decimal('0.01'):
                return self.error_response("Discount too high, price would be ≤ 0", status_code=400)
            product.discounted_market_price = new_price
            product.discount_percentage = discount_value
            product.discount_amount = Decimal('0.00')

        else:  # amount
            # new_price = product.market_price - discount_value
            new_price = base_price - discount_value
            if new_price < Decimal('0.01'):
                return self.error_response("Discount too high, price would be ≤ 0", status_code=400)
            product.discounted_market_price = new_price
            product.discount_amount = discount_value
            product.discount_percentage = Decimal('0.00')

        product.save(update_fields=['market_price','discounted_market_price', 'discount_percentage', 'discount_amount'])

        return self.success_response(
            data={
                "product_id": product.id,
                "product_name": product.name,
                "market_price": str(product.market_price),        # ✅ base price
                "discounted_market_price": str(product.discounted_market_price), # ✅ after discount
                "discount_type": discount_type,
                "discount_value": str(discount_value),
            },
            message="Discount applied to product",
            status_code=200
        )

    @transaction.atomic
    def delete(self, request, product_id):
        user = request.user

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)

        try:
            product = ShopProduct.objects.get(
                id=product_id,
                retailer=user.retailer_profile
            )
        except ShopProduct.DoesNotExist:
            return self.error_response("Product not found", status_code=404)

        if not product.discounted_market_price:
            return self.error_response("This product has no active discount", status_code=400)

        product.discounted_market_price = None
        product.discount_percentage = Decimal('0.00')
        product.discount_amount = Decimal('0.00')

        product.save(update_fields=[
            'discounted_market_price',
            'discount_percentage',
            'discount_amount'
        ])

        return self.success_response(
            data={
                "product_id": product.id,
                "product_name": product.name,
                "market_price": str(product.market_price),
                "discount_removed": True
            },
            message=f"Discount removed from {product.name}",
            status_code=200
        )

#===================================================================================================\

class RetailerSetProductPromoView(StandardResponseMixin, APIView):
    """
    Set or clear promo on a SINGLE product.
    POST   → set promo
    DELETE → clear promo
    """
    permission_classes = [IsAuthenticated]

    def _get_product(self, request, product_id):
        user = request.user
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return None, self.error_response("Unauthorized", status_code=403)
        try:
            product = ShopProduct.objects.get(
                id=product_id,
                retailer=user.retailer_profile
            )
            return product, None
        except ShopProduct.DoesNotExist:
            return None, self.error_response("Product not found", status_code=404)

    def post(self, request, product_id):
        product, err = self._get_product(request, product_id)
        if err:
            return err

        serializer = ProductPromoSerializer(data=request.data)
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        product.promo_buy_quantity = serializer.validated_data['promo_buy_quantity']
        product.promo_free_quantity = serializer.validated_data['promo_free_quantity']
        product.promo_is_active = True
        product.save(update_fields=[
            'promo_buy_quantity', 'promo_free_quantity', 'promo_is_active'
        ])

        return self.success_response(
            data={
                'product_id': product.id,
                'product_name': product.name,
                'promo_label': f"Buy {product.promo_buy_quantity} Get {product.promo_free_quantity} Free",
                'promo_is_active': True
            },
            message="Promo set successfully",
            status_code=200
        )

    def delete(self, request, product_id):
        product, err = self._get_product(request, product_id)
        if err:
            return err
        if product.promo_is_active == True:
            product.promo_buy_quantity = None
            product.promo_free_quantity = None
            product.promo_is_active = False
            product.save(update_fields=[
                'promo_buy_quantity', 'promo_free_quantity', 'promo_is_active'
            ])

            return self.success_response(
                message=f"Promo cleared from '{product.name}'",
                status_code=200
            )
        else: 
            return self.error_response(
                message=f"The product '{product.name}' has no ongoing promotion",
                status_code=400
            )


class RetailerBulkPromoView(StandardResponseMixin, APIView):
    """
    Set or clear promo on ALL products or SPECIFIC products by ID list.
    POST   → set promo   (body: promo_buy_quantity, promo_free_quantity, product_ids[])
    DELETE → clear promo (body: product_ids[] — empty means clear all)
    """
    permission_classes = [IsAuthenticated]

    def _get_retailer(self, request):
        user = request.user
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return None, self.error_response("Unauthorized", status_code=403)
        return user.retailer_profile, None

    @transaction.atomic
    def post(self, request):
        retailer, err = self._get_retailer(request)
        if err:
            return err

        serializer = BulkPromoSerializer(data=request.data)
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        buy_qty  = serializer.validated_data['promo_buy_quantity']
        free_qty = serializer.validated_data['promo_free_quantity']
        product_ids = serializer.validated_data.get('product_ids', [])

        queryset = ShopProduct.objects.filter(retailer=retailer)
        if product_ids:
            queryset = queryset.filter(id__in=product_ids)

        count = queryset.count()
        if count == 0:
            return self.error_response("No products found", status_code=404)

        queryset.update(
            promo_buy_quantity=buy_qty,
            promo_free_quantity=free_qty,
            promo_is_active=True
        )

        scope = f"{count} specific products" if product_ids else f"all {count} products"
        return self.success_response(
            data={
                'products_affected': count,
                'promo_label': f"Buy {buy_qty} Get {free_qty} Free",
                'scope': scope
            },
            message=f"Promo applied to {count} products",
            status_code=200
        )

    @transaction.atomic
    def delete(self, request):
        retailer, err = self._get_retailer(request)
        if err:
            return err

        product_ids = request.data.get('product_ids', [])
        queryset = ShopProduct.objects.filter(retailer=retailer)
        if product_ids:
            queryset = queryset.filter(id__in=product_ids)

        count = queryset.count()
        queryset.update(
            promo_buy_quantity=None,
            promo_free_quantity=None,
            promo_is_active=False
        )

        return self.success_response(
            data={'products_affected': count},
            message=f"Promo cleared from {count} products",
            status_code=200
        )


class RetailerPromoListView(StandardResponseMixin, APIView):
    """
    GET: See all products that currently have an active promo.
    Useful for the retailer dashboard promo management screen.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized", status_code=403)

        products = ShopProduct.objects.filter(
            retailer=user.retailer_profile,
            promo_is_active=True
        )

        data = [
            {
                'product_id': p.id,
                'product_name': p.name,
                'market_price': str(p.market_price),
                'promo_buy_quantity': p.promo_buy_quantity,
                'promo_free_quantity': p.promo_free_quantity,
                'promo_label': f"Buy {p.promo_buy_quantity} Get {p.promo_free_quantity} Free"
            }
            for p in products
        ]

        return self.success_response(
            data={'promos': data, 'total_count': len(data)},
            message="Active promos retrieved",
            status_code=200
        )
















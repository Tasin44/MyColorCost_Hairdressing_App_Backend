from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.contrib.auth import get_user_model
from decimal import Decimal

from authapp.models import SubUser
from retailerapp.models import RetailerProfile, MissingProduct
from affiliateapp.models import Referral, ReferralCode, CommissionWithdrawal
from paymentapp.models import Payment
from affiliateapp.models import Subscription

User = get_user_model()

from .serializers import (
    DashboardStatsSerializer,
    UserListSerializer,
    RetailerDetailSerializer,
    RetailerApprovalSerializer,
    AffiliateUserSerializer,
    OrderListSerializer,
    MissingProductRequestSerializer
)


class StandardResponseMixin:
    """Mixin for consistent API responses"""
    def success_response(self, data=None, message="Success", status_code=200):
        return Response({
            "success": True,
            "message": message,
            "data": data
        }, status=status_code)
    
    def error_response(self, message="Error", status_code=400, data=None):
        return Response({
            "success": False,
            "message": message,
            "data": data
        }, status=status_code)


class AdminDashboardStatsView(StandardResponseMixin, APIView):
    """Get dashboard overview statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get admin dashboard stats"""
        user = request.user
        
        # Check if user is admin/superuser
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        '''
        # Total revenue (platform fees)
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(Sum('platform_fee'))['platform_fee__sum'] or Decimal('0.00')
        
        # Total users (exclude retailers)
        total_users = User.objects.exclude(role='retailer').count()
        
        # Total subscribers
        total_subscribers = Subscription.objects.filter(
            is_active=True
        ).count()
        
        # Total retailers
        total_retailers = RetailerProfile.objects.count()
        '''
        # ✅ SUBSCRIPTION REVENUE
        # Sum of subscription_amount from completed subscriptions
        subscription_revenue = Subscription.objects.filter(
            status='active',
            is_active=True
        ).aggregate(
            total=Sum('subscription_amount')
        )['total'] or Decimal('0.00')
        
        # ✅ SHOP REVENUE (Platform Fee)
        # Platform fee from completed payments (checkout sessions)
        shop_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(
            total=Sum('platform_fee')
        )['total'] or Decimal('0.00')
        
        # ✅ TOTAL REVENUE
        total_revenue = subscription_revenue + shop_revenue
        
        # ✅ Additional Stats
        total_users = User.objects.filter(role__in=['owner', 'self_employed' ,'staff','retailer']).count()
        total_subscribers = Subscription.objects.filter(
            is_active=True
        ).values('user').distinct().count()
        total_retailers = User.objects.filter(role='retailer').count()
        
        stats = {
            'total_revenue': total_revenue,
            'subscription_revenue': subscription_revenue,
            'shop_revenue': shop_revenue,
            'total_users': total_users,
            'total_subscribers': total_subscribers,
            'total_retailers': total_retailers
        }
        
        serializer = DashboardStatsSerializer(data=stats)
        serializer.is_valid()
        
        return self.success_response(
            data=serializer.data,
            message="Dashboard stats retrieved"
        )

        

class AdminUserListView(StandardResponseMixin, APIView):
    """List all users (Section 1)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all users"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        # Get all users except retailers
        users = User.objects.exclude(role='retailer').order_by('-created_at')
        
        # Filter by role if provided
        role = request.query_params.get('role')
        if role in ['owner', 'self_employed', 'staff']:
            users = users.filter(role=role)
        
        users_data = []
        for u in users:
            staff_count = 0
            if u.role == 'owner':
                staff_count = SubUser.objects.filter(
                    main_user=u,
                    is_active=True
                ).count()
            
            users_data.append({
                'id': str(u.id),
                'name': u.name or u.email.split('@')[0],
                'email': u.email,
                'contact_number': u.contact_number or 'N/A',
                'role': u.get_role_display(),
                'staff_count': staff_count,
                'created_at': u.created_at
            })
        
        serializer = UserListSerializer(users_data, many=True)
        
        return self.success_response(
            data={
                'users': serializer.data,
                'total_count': len(users_data)
            },
            message="Users retrieved"
        )


class AdminRetailerListView(StandardResponseMixin, APIView):
    """List all retailers (Section 2)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all retailers"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        # Filter by approval status
        status_filter = request.query_params.get('status', 'all')
        
        retailers = RetailerProfile.objects.select_related('user').order_by('-created_at')
        
        if status_filter == 'approved':
            retailers = retailers.filter(is_approved=True)
        elif status_filter == 'pending':
            retailers = retailers.filter(is_approved=False)
        
        retailers_data = []
        for retailer in retailers:
            retailers_data.append({
                'id': retailer.id,
                'user_id': str(retailer.user.id),
                'name': retailer.user.name or retailer.user.email.split('@')[0],
                'email': retailer.user.email,
                'contact_number': retailer.user.contact_number or 'N/A',
                'business_name': retailer.business_name,
                'delivery_charge': retailer.delivery_charge,
                'free_delivery_threshold': retailer.free_delivery_threshold,
                'total_orders': retailer.total_orders,
                'total_sales': retailer.total_sales,
                'total_pending': retailer.total_pending,
                'total_cancelled': retailer.total_cancelled,
                'api_key': retailer.api_key or 'N/A',
                'is_approved': retailer.is_approved,
                'stripe_account_id': retailer.stripe_account_id or 'N/A',
                'stripe_connected': retailer.stripe_connected,
                'stripe_connection_date': retailer.stripe_connection_date,
                'created_at': retailer.created_at
            })
        
        serializer = RetailerDetailSerializer(retailers_data, many=True)
        
        return self.success_response(
            data={
                'retailers': serializer.data,
                'total_count': len(retailers_data)
            },
            message="Retailers retrieved"
        )


class AdminRetailerApprovalView(StandardResponseMixin, APIView):
    """Approve/reject retailer"""
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, retailer_id):
        """Update retailer approval status"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        try:
            retailer = RetailerProfile.objects.get(id=retailer_id)
        except RetailerProfile.DoesNotExist:
            return self.error_response("Retailer not found", status_code=404)
        
        serializer = RetailerApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self.error_response(
                "Invalid data",
                status_code=400,
                data=serializer.errors
            )
        
        retailer.is_approved = serializer.validated_data['is_approved']
        retailer.save(update_fields=['is_approved'])
        
        return self.success_response(
            data={
                'retailer_id': retailer.id,
                'is_approved': retailer.is_approved
            },
            message="Retailer status updated"
        )


class AdminAffiliateUserListView(StandardResponseMixin, APIView):
    """List affiliate users (Section 3)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get affiliate users statistics"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        # Get users who have referrals
        referrers = User.objects.filter(
            referrals_made__isnull=False
        ).distinct()
        
        affiliate_data = []
        for referrer in referrers:
            # Get referral code
            try:
                ref_code = referrer.referral_code.code
            except:
                ref_code = 'N/A'
            
            # Count referrals
            total_referrals = Referral.objects.filter(referrer=referrer).count()
            
            # Withdrawn amount
            withdrawn = CommissionWithdrawal.objects.filter(
                user=referrer,
                status='completed'
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            
            affiliate_data.append({
                'id': str(referrer.id),
                'name': referrer.name or referrer.email.split('@')[0],
                'email': referrer.email,
                'referral_code': ref_code,
                'total_referrals': total_referrals,
                'total_earned': referrer.total_commission_earned,
                'withdrawn_amount': withdrawn,
                'pending_balance': referrer.available_commission
            })
        
        serializer = AffiliateUserSerializer(affiliate_data, many=True)
        
        return self.success_response(
            data={
                'affiliates': serializer.data,
                'total_count': len(affiliate_data)
            },
            message="Affiliate users retrieved"
        )


class AdminOrderListView(StandardResponseMixin, APIView):
    """List all orders (Section 4)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all orders"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        # Get all payments
        payments = Payment.objects.select_related('user').order_by('-created_at')
        
        orders_data = []
        for payment in payments:
            # Count total products
            from paymentapp.models import RetailerOrder
            product_count = RetailerOrder.objects.filter(payment=payment).count()
            
            orders_data.append({
                'order_id': payment.id,
                'user_name': payment.user.name or payment.user.email.split('@')[0],
                'user_email': payment.user.email,
                'order_date': payment.created_at,
                'product_quantity': product_count,
                'total_amount': payment.total_amount,
                'platform_fee': payment.platform_fee,
                'status': payment.status
            })
        
        serializer = OrderListSerializer(orders_data, many=True)
        
        return self.success_response(
            data={
                'orders': serializer.data,
                'total_count': len(orders_data),
                'total_commission': sum(o['platform_fee'] for o in orders_data)
            },
            message="Orders retrieved"
        )


class AdminMissingProductListView(StandardResponseMixin, APIView):
    """List missing product requests (Section 5)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get missing product requests"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        # Filter by status
        status_filter = request.query_params.get('status', 'all')
        
        missing_products = MissingProduct.objects.select_related(
            'requested_by'
        ).order_by('-created_at')
        
        if status_filter in ['pending', 'added', 'rejected']:
            missing_products = missing_products.filter(status=status_filter)
        
        products_data = []
        for mp in missing_products:
            products_data.append({
                'id': mp.id,
                'requested_by_name': mp.requested_by.name or mp.requested_by.email.split('@')[0],
                'requested_by_email': mp.requested_by.email,
                'product_name': mp.product_name,
                'category': mp.category or 'N/A',
                'brand': mp.brand or 'N/A',
                'additional_notes': mp.additional_notes or 'N/A',
                'status': mp.get_status_display(),
                'created_at': mp.created_at
            })
        
        serializer = MissingProductRequestSerializer(products_data, many=True)
        
        return self.success_response(
            data={
                'products': serializer.data,
                'total_count': len(products_data)
            },
            message="Missing products retrieved"
        )


class AdminMissingProductUpdateView(StandardResponseMixin, APIView):
    """Update missing product status"""
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, product_id):
        """Update status"""
        user = request.user
        
        if not user.is_staff and not user.is_superuser:
            return self.error_response("Unauthorized access", status_code=403)
        
        try:
            missing_product = MissingProduct.objects.get(id=product_id)
        except MissingProduct.DoesNotExist:
            return self.error_response("Product request not found", status_code=404)
        
        new_status = request.data.get('status')
        
        if new_status not in ['pending', 'added', 'rejected']:
            return self.error_response("Invalid status", status_code=400)
        
        missing_product.status = new_status
        missing_product.save(update_fields=['status'])
        
        return self.success_response(
            data={
                'product_id': missing_product.id,
                'status': missing_product.status
            },
            message="Status updated"
        )
    




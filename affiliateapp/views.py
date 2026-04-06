from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

from .models import ReferralCode, Referral, CommissionWithdrawal, Subscription
from .serializers import (
    ReferralStatsSerializer,
    CommissionWithdrawalSerializer,
    SubscriptionSerializer,ReferrerPublicProfileSerializer,
    SubscriptionCreateSerializer  # ✅ Add this import
)


# Create your views here.

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
    
    
class ReferralDashboardView(StandardResponseMixin, APIView):
    """Get user's referral statistics and earnings"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get referral code
        try:
            referral_code = user.referral_code.code
        except ReferralCode.DoesNotExist:
            # Generate if missing
            import secrets
            import string
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            while ReferralCode.objects.filter(code=code).exists():
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            ReferralCode.objects.create(user=user, code=code)
            referral_code = code
        
        # Stats
        referrals = Referral.objects.filter(referrer=user)
        total_referrals = referrals.count()
        active_referrals = referrals.filter(status='active').count()
        
        pending_withdrawals = CommissionWithdrawal.objects.filter(
            user=user,
            status__in=['pending', 'approved', 'processing']
        ).count()
        
        stats = {
            'referral_code': referral_code,
            'total_referrals': total_referrals,
            'active_referrals': active_referrals,
            'total_commission_earned': str(user.total_commission_earned),
            'available_commission': str(user.available_commission),
            'pending_withdrawals': pending_withdrawals
        }
        
        serializer = ReferralStatsSerializer(data=stats)
        serializer.is_valid()
        
        return self.success_response(
            data=serializer.data,
            message="Referral statistics retrieved"
        )


class WithdrawalRequestView(StandardResponseMixin, APIView):
    """Request commission withdrawal"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = CommissionWithdrawalSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = request.user
            amount = serializer.validated_data['amount']
            
            # Deduct from available balance
            user.available_commission -= amount
            user.save(update_fields=['available_commission'])
            
            # Create withdrawal request
            withdrawal = serializer.save(user=user)
            
            return self.success_response(
                data=CommissionWithdrawalSerializer(withdrawal).data,
                message="Withdrawal request submitted successfully",
                status_code=201
            )
        
        return self.error_response(
            "Invalid withdrawal request",
            status_code=400,
            data=serializer.errors
        )
    
    def get(self, request):
        """Get user's withdrawal history"""
        withdrawals = CommissionWithdrawal.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        serializer = CommissionWithdrawalSerializer(withdrawals, many=True)
        
        return self.success_response(
            data=serializer.data,
            message="Withdrawal history retrieved"
        )


class SubscriptionStatusView(StandardResponseMixin, APIView):
    """Check user's subscription status"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Free-access override from admin
        if user.has_active_subscription:
            return self.success_response(
                data={
                    "is_subscribed": True,
                    "plan_type": "free_access",
                    "status": "active",
                    "subscription_details": None
                },
                message="Subscription status retrieved"
            )
        
        try:
            subscription = user.subscription
            serializer = SubscriptionSerializer(subscription)

            # ✅ Check if subscription is truly active
            is_active = (
                subscription.is_active and 
                subscription.status == 'active' and
                subscription.subscription_end_date and
                subscription.subscription_end_date > timezone.now()
            )
            # ✅ Enhanced response with plan info
            return self.success_response(
                data={
                    #'is_subscribed': subscription.is_active,
                    'is_subscribed': is_active,  # ✅ Use computed value
                    'plan_type': subscription.plan_type,
                    'status': subscription.status,
                    'subscription_details': serializer.data
                },
                message="Subscription status retrieved"
            )
        except Subscription.DoesNotExist:
            return self.success_response(
                data={
                    'is_subscribed': False,
                    'plan_type': None,
                    'status': 'none',
                    'message': 'No active subscription'
                },
                message="No subscription found"
            )



#========================================================
#Revenue cat webhook handler 

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
from decimal import Decimal
from django.contrib.auth import get_user_model

@csrf_exempt
def revenuecat_webhook(request):
    """
    Handle RevenueCat webhook events
    Docs: https://www.revenuecat.com/docs/webhooks
    """
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    try:
        payload = json.loads(request.body)
        event_type = payload.get('event', {}).get('type')
        
        # Extract user data
        app_user_id = payload.get('event', {}).get('app_user_id')
        product_id = payload.get('event', {}).get('product_id')
        price_in_purchased_currency = payload.get('event', {}).get('price_in_purchased_currency', 0)
        
        # Google Play takes 15% for first $1M, then 30%
        google_fee_rate = Decimal('0.15')  # Adjust based on your tier
        net_amount = Decimal(str(price_in_purchased_currency)) * (Decimal('1.00') - google_fee_rate)
        
        try:
            user = User.objects.get(id=app_user_id)
        except User.DoesNotExist:
            return HttpResponse(status=404)
        
        # Handle different events
        if event_type == 'INITIAL_PURCHASE':
            # User subscribed after trial
            handle_subscription_purchase(user, payload, net_amount)
        
        elif event_type == 'RENEWAL':
            # Subscription renewed
            handle_subscription_renewal(user, payload, net_amount)
        
        elif event_type == 'CANCELLATION':
            # Subscription cancelled
            handle_subscription_cancellation(user, payload)
        
        elif event_type == 'EXPIRATION':
            # Subscription expired
            handle_subscription_expiration(user, payload)
        
        return HttpResponse(status=200)
    
    except Exception as e:
        print(f"RevenueCat webhook error: {str(e)}")
        return HttpResponse(status=500)


@transaction.atomic
def handle_subscription_purchase(user, payload, net_amount):
    """Handle initial subscription purchase"""
    from datetime import datetime

    # ✅ Extract plan type from product_id
    product_id = payload['event']['product_id']
    plan_type = 'monthly' if 'month' in product_id.lower() else 'yearly'
    
    # Update or create subscription
    subscription, created = Subscription.objects.update_or_create(
        user=user,
        defaults={
            'revenuecat_customer_id': payload['event']['app_user_id'],
            #'product_id': payload['event']['product_id'],
            'product_id': product_id,
            'plan_type': plan_type,  # ✅ Add this
            'status': 'active',
            'subscription_start_date': timezone.now(),
            'subscription_end_date': datetime.fromtimestamp(
                payload['event']['expiration_at_ms'] / 1000
            ),
            'subscription_amount': Decimal(str(payload['event']['price_in_purchased_currency'])),
            'net_amount': net_amount,
            'is_active': True
        }
    )
    
    # Update user subscription status
    user.has_active_subscription = True
    user.subscription_expires_at = subscription.subscription_end_date
    user.save(update_fields=['has_active_subscription', 'subscription_expires_at'])
    
    # Process referral commission (25%)
    try:
        referral = Referral.objects.get(referred_user=user, status='pending')
        commission = net_amount * (referral.commission_rate / Decimal('100'))
        
        # Update referral
        referral.commission_earned += commission
        referral.status = 'active'
        referral.save()
        
        # Update referrer's balance
        referrer = referral.referrer
        referrer.total_commission_earned += commission
        referrer.available_commission += commission
        referrer.save(update_fields=['total_commission_earned', 'available_commission'])
    except Referral.DoesNotExist:
        pass  # No referral for this user


@transaction.atomic
def handle_subscription_renewal(user, payload, net_amount):
    """Handle subscription renewal"""
    # Similar to purchase, but update existing subscription
    handle_subscription_purchase(user, payload, net_amount)


@transaction.atomic
def handle_subscription_cancellation(user, payload):
    """Handle subscription cancellation"""
    try:
        subscription = user.subscription
        subscription.status = 'cancelled'
        subscription.save()
        
        # Don't disable immediately - let it expire naturally
    except Subscription.DoesNotExist:
        pass


@transaction.atomic
def handle_subscription_expiration(user, payload):
    """Handle subscription expiration"""
    try:
        subscription = user.subscription
        subscription.status = 'expired'
        subscription.is_active = False
        subscription.save()
        
        # Update user status
        user.has_active_subscription = False
        user.save(update_fields=['has_active_subscription'])
    except Subscription.DoesNotExist:
        pass

from django.http import JsonResponse
from django.utils import timezone

class SubscriptionMiddleware:
    """
    Check subscription status for protected endpoints
    """
    EXEMPT_URLS = [
        '/api/auth/',
        '/api/subscription/status/',
        '/admin/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if URL is exempt
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return self.get_response(request)
        
        # Check if user is authenticated
        if request.user.is_authenticated:
            # Check subscription
            if not request.user.has_active_subscription:
                if request.user.subscription_expires_at and request.user.subscription_expires_at < timezone.now():
                    return JsonResponse({
                        'success': False,
                        'statusCode': 403,
                        'message': 'Your subscription has expired. Please renew to continue.',
                        'data': {'subscription_expired': True}
                    }, status=403)
        
        return self.get_response(request)
    

class MyReferralCodeView(StandardResponseMixin, APIView):
    """Get user's unique referral code"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        try:
            referral_code = user.referral_code.code
        except ReferralCode.DoesNotExist:
            # Generate if somehow missing
            import secrets
            import string
            
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            while ReferralCode.objects.filter(code=code).exists():
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            
            ReferralCode.objects.create(user=user, code=code)
            referral_code = code

        # ✅ Build the referral URL
        referral_url = request.build_absolute_uri(
            f'/affiliate/referral/join/?code={referral_code}'
        )

        return self.success_response(
            data={
                'referral_code': referral_code,
                'referral_url': referral_url,  # ✅ Added this
                'share_message': f'Join My Color Cost using my code: {referral_code}'
            },
            message="Referral code retrieved successfully"
        )
    
#=============================================================================================

from django.shortcuts import render
from django.views.generic import TemplateView

class ReferralLandingPageView(TemplateView):
    """Public landing page for referral links - NO AUTHENTICATION REQUIRED"""
    template_name = 'affiliateapp/referral_landing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        referral_code = self.request.GET.get('code', '')
        
        try:
            # Get referral code object
            ref_code_obj = ReferralCode.objects.select_related('user').get(code=referral_code)
            user = ref_code_obj.user
            
            # Build profile data
            context['referrer'] = {
                'name': user.get_full_name() or user.email.split('@')[0],
                'email': user.email,
                'profile_image': user.profile_image.url if hasattr(user, 'profile_image') and user.profile_image else None,
                'referral_code': referral_code
            }
            context['valid'] = True
            
        except ReferralCode.DoesNotExist:
            context['valid'] = False
            context['error_message'] = 'Invalid referral code'
        
        return context


class ReferralLandingAPIView(StandardResponseMixin, APIView):
    """API endpoint to get referrer info - NO AUTHENTICATION REQUIRED"""
    permission_classes = []  # Public endpoint
    
    def get(self, request):
        referral_code = request.GET.get('code', '').strip()
        
        if not referral_code:
            return self.error_response(
                "Referral code is required",
                status_code=400
            )
        
        try:
            # Get referral code object
            ref_code_obj = ReferralCode.objects.select_related('user').get(code=referral_code)
            user = ref_code_obj.user
            
            # Build response data
            data = {
                'name': user.get_full_name() or user.email.split('@')[0],
                'email': user.email,
                'profile_image': user.profile_image.url if hasattr(user, 'profile_image') and user.profile_image else None,
                'referral_code': referral_code
            }
            
            serializer = ReferrerPublicProfileSerializer(data=data)
            serializer.is_valid()
            
            return self.success_response(
                data=serializer.data,
                message="Referrer profile retrieved successfully"
            )
            
        except ReferralCode.DoesNotExist:
            return self.error_response(
                "Invalid referral code",
                status_code=404
            )



class CreateSubscriptionView(StandardResponseMixin, APIView):
    """
    POST: Create subscription with referral tracking
    Expected payload:
    {
        "user_id": 123,
        "referral_code": "ABC12345",
        "subscription_plan": "monthly" or "yearly"
    }
    """
    """
    POST: Create subscription with referral tracking
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = SubscriptionCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self.error_response(
                "Invalid data",
                status_code=400,
                data=serializer.errors
            )
        
        user_id = serializer.validated_data['user_id']
        referral_code = serializer.validated_data.get('referral_code')  # ✅ Use .get() instead of ['referral_code']
        plan_type = serializer.validated_data['subscription_plan']
        
        try:
            user = User.objects.get(id=user_id)
            
            # ✅ Only process referral if code is provided
            if referral_code:
                ref_code_obj = ReferralCode.objects.get(code=referral_code)
                
                # Check if user is trying to use their own code
                if ref_code_obj.user == user:
                    return self.error_response(
                        "Cannot use your own referral code",
                        status_code=400
                    )
                
                # Create or update referral relationship
                referral, created = Referral.objects.get_or_create(
                    referrer=ref_code_obj.user,
                    referred_user=user,
                    referral_code=ref_code_obj,
                    defaults={
                        'status': 'pending',
                        'commission_rate': Decimal('25.00')
                    }
                )
            # ✅ Calculate end date
            from datetime import timedelta
            start_date = timezone.now()
            end_date = start_date + timedelta(days=30 if plan_type == 'monthly' else 365)
            # Create/Update subscription
            subscription, sub_created = Subscription.objects.update_or_create(
                user=user,
                # defaults={
                #     'plan_type': plan_type,
                #     'status': 'trial',
                #     'revenuecat_customer_id': f"user_{user_id}",
                #     'product_id': f"{plan_type}_plan",
                #     'is_active': False
                # }
            defaults={
                'plan_type': plan_type,
                'status': 'active',  # ✅ Changed from 'trial'
                'is_active': True,   # ✅ Changed from False
                'subscription_start_date': start_date,
                'subscription_end_date': end_date,
                'revenuecat_customer_id': f"user_{user_id}",
                'product_id': f"{plan_type}_plan",
                'subscription_amount': Decimal('9.99') if plan_type == 'monthly' else Decimal('99.99'),
            }
            )
                    # ✅ Update user subscription status
            user.has_active_subscription = True
            user.subscription_expires_at = end_date
            user.save(update_fields=['has_active_subscription', 'subscription_expires_at'])
            return self.success_response(
                data={
                    'message': 'Subscription initialized',
                    'referral_used': bool(referral_code),  # ✅ Indicate if referral was used
                    'plan_type': plan_type,
                    'subscription_status': subscription.status,
                    'is_active': subscription.is_active,
                    'expires_at': end_date.isoformat()
                },
                message="Subscription created successfully",
                status_code=201
            )
            
        except User.DoesNotExist:
            return self.error_response("User not found", status_code=404)
        except ReferralCode.DoesNotExist:
            return self.error_response("Invalid referral code", status_code=404)
        except Exception as e:
            return self.error_response(
                f"Error creating subscription: {str(e)}",
                status_code=500
            )

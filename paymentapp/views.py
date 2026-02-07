from django.shortcuts import render

# Create your views here.
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from decimal import Decimal
from mixapp.models import ShoppingCart

stripe.api_key = settings.STRIPE_SECRET_KEY
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

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


class CreateCheckoutSessionView(StandardResponseMixin, APIView):
    """Create Stripe checkout session for cart"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        user = request.user
        delivery_address_id = request.data.get('delivery_address_id')
        
        # Get cart items
        cart_items = ShoppingCart.objects.filter(user=user).select_related(
            'shop_product__retailer'
        )
        
        if not cart_items.exists():
            return self.error_response("Cart is empty", status_code=400)
        
        # Group by retailer
        retailer_data = {}
        total_amount = Decimal('0.00')
        
        for item in cart_items:
            retailer = item.shop_product.retailer
            
            if not retailer or not retailer.stripe_connected:
                return self.error_response(
                    f"Retailer for {item.shop_product.name} not connected to Stripe",
                    status_code=400
                )
            
            if retailer.id not in retailer_data:
                retailer_data[retailer.id] = {
                    'retailer': retailer,
                    'products': [],
                    'product_total': Decimal('0.00'),
                    'delivery_charge': retailer.delivery_charge
                }
            
            product_total = item.shop_product.market_price * item.quantity
            retailer_data[retailer.id]['products'].append({
                'name': item.shop_product.name,
                'quantity': item.quantity,
                'price': item.shop_product.market_price,
                'total': product_total
            })
            retailer_data[retailer.id]['product_total'] += product_total
            total_amount += product_total
        
        # Calculate delivery
        total_delivery = sum(r['delivery_charge'] for r in retailer_data.values())
        
        # Distribute delivery if > £5
        if total_delivery > Decimal('5.00'):
            for retailer_id, data in retailer_data.items():
                proportion = data['product_total'] / total_amount
                data['delivery_share'] = (total_delivery * proportion).quantize(Decimal('0.01'))
        else:
            for data in retailer_data.values():
                data['delivery_share'] = data['delivery_charge']
        
        final_total = total_amount + total_delivery
        platform_fee = (final_total * Decimal(str(settings.STRIPE_PLATFORM_FEE_PERCENT)) / Decimal('100')).quantize(Decimal('0.01'))
        
        # Create Payment record
        from paymentapp.models import Payment
        payment = Payment.objects.create(
            user=user,
            total_amount=final_total,
            platform_fee=platform_fee,
            delivery_charge=total_delivery,
            status='pending'
        )
        
        # Create Stripe checkout session
        try:
            line_items = []
            for data in retailer_data.values():
                for product in data['products']:
                    line_items.append({
                        'price_data': {
                            'currency': 'gbp',
                            'product_data': {
                                'name': product['name']
                            },
                            'unit_amount': int(product['price'] * 100)
                        },
                        'quantity': product['quantity']
                    })
            
            # Add delivery as line item
            line_items.append({
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {'name': 'Delivery Charge'},
                    'unit_amount': int(total_delivery * 100)
                },
                'quantity': 1
            })
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=f"{settings.BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.BASE_URL}/payment/cancel",
                metadata={
                    'payment_id': payment.id,
                    'user_id': user.id
                },
                payment_intent_data={
                    'application_fee_amount': int(platform_fee * 100)
                }
            )
            
            payment.checkout_session_id = session.id
            payment.save()
            
            return self.success_response(
                data={
                    'checkout_url': session.url,
                    'session_id': session.id,
                    'payment_id': payment.id
                },
                message="Checkout session created",
                status_code=200
            )
        
        except stripe.error.StripeError as e:
            payment.status = 'failed'
            payment.save()
            return self.error_response(str(e), status_code=500)

# Add to paymentapp/views.py



@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    # Handle payment success
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_successful_payment(session)
    
    return HttpResponse(status=200)


@transaction.atomic
def handle_successful_payment(session):
    """Process successful payment and split to retailers"""
    from paymentapp.models import Payment, PaymentRetailerSplit
    
    payment_id = session['metadata']['payment_id']
    payment = Payment.objects.get(id=payment_id)
    
    payment.payment_intent_id = session['payment_intent']
    payment.status = 'completed'
    payment.save()
    
    # Get cart items grouped by retailer
    cart_items = ShoppingCart.objects.filter(user=payment.user).select_related(
        'shop_product__retailer'
    )
    
    retailer_totals = {}
    total_amount = Decimal('0.00')
    
    for item in cart_items:
        retailer = item.shop_product.retailer
        product_total = item.shop_product.market_price * item.quantity
        
        if retailer.id not in retailer_totals:
            retailer_totals[retailer.id] = {
                'retailer': retailer,
                'product_amount': Decimal('0.00'),
                'delivery_charge': retailer.delivery_charge
            }
        
        retailer_totals[retailer.id]['product_amount'] += product_total
        total_amount += product_total
    
    # Distribute delivery
    total_delivery = sum(r['delivery_charge'] for r in retailer_totals.values())
    if total_delivery > Decimal('5.00'):
        for data in retailer_totals.values():
            proportion = data['product_amount'] / total_amount
            data['delivery_share'] = (total_delivery * proportion).quantize(Decimal('0.01'))
    else:
        for data in retailer_totals.values():
            data['delivery_share'] = data['delivery_charge']
    
    # Transfer to each retailer
    for data in retailer_totals.values():
        retailer = data['retailer']
        product_amount = data['product_amount']
        delivery_share = data['delivery_share']
        subtotal = product_amount + delivery_share
        
        # Calculate platform fee on this retailer's portion
        platform_fee_share = (subtotal * Decimal(str(settings.STRIPE_PLATFORM_FEE_PERCENT)) / Decimal('100')).quantize(Decimal('0.01'))
        transfer_amount = subtotal - platform_fee_share
        
        try:
            # Create Stripe transfer
            transfer = stripe.Transfer.create(
                amount=int(transfer_amount * 100),
                currency='gbp',
                destination=retailer.stripe_account_id,
                transfer_group=payment.payment_intent_id
            )
            
            # Record split
            PaymentRetailerSplit.objects.create(
                payment=payment,
                retailer=retailer,
                product_amount=product_amount,
                delivery_share=delivery_share,
                platform_fee_share=platform_fee_share,
                total_transfer_amount=transfer_amount,
                transfer_id=transfer.id,
                transfer_status='completed'
            )
        
        except stripe.error.StripeError as e:
            # Log error but continue with other transfers
            PaymentRetailerSplit.objects.create(
                payment=payment,
                retailer=retailer,
                product_amount=product_amount,
                delivery_share=delivery_share,
                platform_fee_share=platform_fee_share,
                total_transfer_amount=transfer_amount,
                transfer_status='failed'
            )
    
    # Clear cart
    cart_items.delete()

























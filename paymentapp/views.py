from django.shortcuts import render

# Create your views here.
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from decimal import Decimal
from mixapp.models import ShoppingCart, ShopProduct
from paymentapp.models import Payment, PaymentRetailerSplit, RetailerOrder

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


# REPLACE CreateCheckoutSessionView with this

class CreateCheckoutSessionView(StandardResponseMixin, APIView):
    """Create delivery address and checkout session in one request"""
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """
        Combined: Create address + checkout
        
        Request body:
        - address_label: "Home" / "Office" / "Salon"
        - full_address: Full address text
        - area: Area name
        - postal_code: Postal code
        - phone_number: Phone number
        - is_default: true/false (optional)
        """
        user = request.user

        # ✅ Step 1: Validate products from request
        products_data = request.data.get('products', [])
        if not products_data:
            return self.error_response("Products list is required", status_code=400)
        
        # Step 1: Create/Get delivery address
        from retailerapp.models import CustomerDeliveryAddress
        from retailerapp.serializers import CustomerDeliveryAddressSerializer
        
        address_data = {
            'address_label': request.data.get('address_label'),
            'full_address': request.data.get('full_address'),
            'area': request.data.get('area'),
            'postal_code': request.data.get('postal_code'),
            'phone_number': request.data.get('phone_number'),
            'is_default': request.data.get('is_default', False)
        }
        
        # Validate address
        address_serializer = CustomerDeliveryAddressSerializer(
            data=address_data,
            context={'request': request}
        )
        
        if not address_serializer.is_valid():
            return self.error_response(
                "Invalid address data",
                status_code=400,
                data=address_serializer.errors
            )
        
        # Create address
        delivery_address = address_serializer.save()
        
        '''
        # Step 2: Get cart items
        cart_items = ShoppingCart.objects.filter(user=user).select_related(
            'shop_product__retailer'
        )
        
        if not cart_items.exists():
            delivery_address.delete()  # Rollback address
            return self.error_response("Cart is empty", status_code=400)
        
        '''
        # ✅ Step 3: Fetch products and validate
        product_ids = [p['shop_product_id'] for p in products_data]
        products = ShopProduct.objects.filter(
            id__in=product_ids
        ).select_related('retailer')
        
        '''
        if products.count() != len(product_ids):
            delivery_address.delete()
            return self.error_response("Some products not found", status_code=400)
        '''

        
        # ✅ Step 4: Build product map with quantities
        product_quantity_map = {p['shop_product_id']: p['quantity'] for p in products_data}

        # ✅ NEW: Validate stock availability BEFORE processing
        for product in products:
            requested_quantity = product_quantity_map.get(product.id, 0)
            
            if requested_quantity == 0:
                delivery_address.delete()
                return self.error_response(
                    f"Quantity not found for product {product.name}",
                    status_code=400
                )
            
            # ✅ Check if enough stock available
            if product.quantity < requested_quantity:
                delivery_address.delete()
                return self.error_response(
                    f"Insufficient stock for {product.name}. Available: {product.quantity}, Requested: {requested_quantity}",
                    status_code=400
                )
            
            # ✅ Check if product is out of stock
            if product.stock_status == 'out_of_stock' or product.quantity <= 0:
                delivery_address.delete()
                return self.error_response(
                    f"Product {product.name} is out of stock",
                    status_code=400
                )
            
        # Step 3: Group by retailer and calculate totals
        retailer_data = {}
        total_amount = Decimal('0.00')
        response_products = []  # ✅ NEW: Store for response

        '''
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
        '''
        for product in products:
            retailer = product.retailer
            #quantity = product_quantity_map[product.id]
            quantity = product_quantity_map.get(product.id, 0)
            if quantity == 0:
                delivery_address.delete()
                return self.error_response(
                    f"Quantity not found for product {product.name}",
                    status_code=400
                )

            if not retailer or not retailer.stripe_connected:
                delivery_address.delete()
                return self.error_response(
                    f"Retailer for the product '{product.name}' not connected to Stripe",
                    status_code=400
                )
            
            if retailer.id not in retailer_data:
                retailer_data[retailer.id] = {
                    'retailer': retailer,
                    'products': [],
                    'product_total': Decimal('0.00'),
                    'delivery_charge': retailer.delivery_charge
                }

            #This is the only place money is calculated. 
            #product_total = product.market_price * quantity

            #changed the above line with the below snippet for promo
            #========================================================================\
            if product.discounted_market_price!='null': 
                unit_price=product.discounted_market_price
            else: 
                unit_price=product.market_price
            # ✅ Apply Buy X Get Y Free promo if active
            if (product.promo_is_active
                    and product.promo_buy_quantity
                    and product.promo_free_quantity):
                from retailerapp.promo_utils import calculate_promo_price
                product_total = calculate_promo_price(
                    unit_price=unit_price,
                    quantity=quantity,
                    promo_buy_qty=product.promo_buy_quantity,
                    promo_free_qty=product.promo_free_quantity
                )
                promo_label = f"Buy {product.promo_buy_quantity} Get {product.promo_free_quantity} Free"
            else:
                product_total = unit_price * quantity
                promo_label = None
            #=========================================================================/
            # retailer_data[retailer.id]['products'].append({
            #     'name': item.shop_product.name,
            #     'quantity': item.quantity,
            #     'price': item.shop_product.market_price,
            #     'total': product_total
            # })
            retailer_data[retailer.id]['products'].append({
            'name': product.name,
            'quantity': quantity,
            'price': unit_price,
            'total': product_total,
            'promo_label': promo_label,      # ✅ e.g. "Buy 5 Get 1 Free" or None
            'product_obj': product  # ✅ ADD THIS for later use
            })
            retailer_data[retailer.id]['product_total'] += product_total
            total_amount += product_total
            # ✅ NEW: Add to response list
            response_products.append({
                'id': product.id,
                'name': product.name,
                'quantity': quantity,
                #'price': str(product.market_price),
                'price': unit_price,
                'subtotal': str(product_total),
                'promo_label': promo_label,        # ✅ show customer what promo was applied
            })
        # Step 4: Calculate delivery charges
        total_delivery = sum(r['delivery_charge'] for r in retailer_data.values())
        
        if total_delivery > Decimal('5.00'):
            for retailer_id, data in retailer_data.items():
                proportion = data['product_total'] / total_amount
                data['delivery_share'] = (total_delivery * proportion).quantize(Decimal('0.01'))
        else:
            for data in retailer_data.values():
                data['delivery_share'] = data['delivery_charge']
        
        final_total = total_amount + total_delivery
        platform_fee = (final_total * Decimal(str(settings.STRIPE_PLATFORM_FEE_PERCENT)) / Decimal('100')).quantize(Decimal('0.01'))
        
        # Step 5: Create Payment record
        from paymentapp.models import Payment
        payment = Payment.objects.create(
            user=user,
            total_amount=final_total,
            platform_fee=platform_fee,
            delivery_charge=total_delivery,
            delivery_address=delivery_address,
            status='pending'
            # ✅ payment_intent_id is NULL/blank initially
        )
        
        # Step 6: Create Stripe checkout session
        try:
            line_items = []
            for data in retailer_data.values():
                for product in data['products']:
                    
                    #================================================================\
                    #Added those lines for promo
                    # ✅ Build display name — include promo label if active
                    display_name = product['name']
                    if product.get('promo_label'):
                        display_name += f" [{product['promo_label']}]"
                    #=============================================================  /

                    line_items.append({
                        'price_data': {
                            'currency': 'gbp',
                            'product_data': {
                                #'name': product['name']
                                'name': display_name          # e.g. "Shampoo [Buy 5 Get 1 Free]"
                            },
                            #'unit_amount': int(product['price'] * 100) # ✅ already discounted total
                            'unit_amount': int(product['total'] * 100),  # ✅ already discounted total (220.00)
                        },
                        #'quantity': product['quantity']# quantity=1 because unit_amount already holds the full total
                        'quantity': 1                                 # ✅ total already includes quantity
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
                    'user_id': user.id,
                    'product_ids': ','.join(map(str, product_ids))  # ✅ NEW: Store product IDs
                },
                # ❌ REMOVE THIS - Checkout Session doesn't support application_fee_amount
                # payment_intent_data={
                #     'application_fee_amount': int(platform_fee * 100)
                # }
            )
            '''
            ❌ ❌ ❌ Error I faced: ❌ ❌ ❌ 
            UNIQUE constraint failed: payments.payment_intent_id
            Request Method: POST
            Request URL: http://10.10.12.14:8000/payment/create-checkout/
            Django Version: 6.0.1
            Exception Type: IntegrityError
            Exception Value:
            UNIQUE constraint failed: payments.payment_intent_id

            Ans: 

            Why This Happens
                Stripe Checkout Session Flow:
                You create checkout session → No payment_intent exists yet
                User pays → Stripe creates payment_intent internally
                Webhook fires → Stripe sends payment_intent_id in webhook data
                You save it → Update Payment record with actual payment_intent_id

            Your Original Code:
                Created Payment with NULL payment_intent_id
                SQLite sees empty string as a value (not NULL)
                Second payment tries to save with empty string → UNIQUE constraint error


            '''
            # ✅ Save session ID (payment_intent_id is still NULL)
            payment.checkout_session_id = session.id
            payment.save()

            # ✅ DEV ONLY: Decrease quantities immediately
            # Remove this code when you deploy to production! (Webhooks will work then)
            from django.db.models import F
            for product_id, quantity in product_quantity_map.items():
                ShopProduct.objects.filter(id=product_id).update(
                    quantity=F('quantity') - quantity
                )

            # Refresh and update stock status
            products_to_update = ShopProduct.objects.filter(id__in=product_quantity_map.keys())
            for product in products_to_update:
                if product.quantity <= 0:
                    product.stock_status = 'out_of_stock'
                elif product.quantity <= 10:
                    product.stock_status = 'low_stock'
                else:
                    product.stock_status = 'in_stock'
                product.save(update_fields=['stock_status'])
            

            #added here ========================================================

            # ✅ NEW: Create RetailerOrder and PaymentRetailerSplit
            for data in retailer_data.values():
                retailer = data['retailer']
                product_amount = data['product_total']
                delivery_share = data['delivery_share']
                subtotal = product_amount + delivery_share
                
                # Calculate platform fee
                platform_fee_share = (subtotal * Decimal(str(settings.STRIPE_PLATFORM_FEE_PERCENT)) / Decimal('100')).quantize(Decimal('0.01'))
                transfer_amount = subtotal - platform_fee_share
                
                transfer_id = None
                transfer_status = 'pending'

                try:
                    # Create Stripe Transfer
                    transfer = stripe.Transfer.create(
                        amount=int(transfer_amount * 100),
                        currency='gbp',
                        destination=retailer.stripe_account_id,# ← in development This is a TEST account ID
                        # transfer_group=payment.payment_intent_id,
                        transfer_group=str(payment.id),  # payment_intent_id is NULL here, use payment.id
                        metadata={
                            'payment_id': payment.id,
                            'retailer_id': retailer.id
                        }
                    )
                    transfer_id = transfer.id
                    transfer_status = 'completed'
                    
                except stripe.error.StripeError as e:
                    # Log error but continue
                    transfer_status = 'failed'
                    print(f"Transfer failed for retailer {retailer.id}: {str(e)}")

                    # Create PaymentRetailerSplit
                    PaymentRetailerSplit.objects.create(
                        payment=payment,
                        retailer=retailer,
                        product_amount=product_amount,
                        delivery_share=delivery_share,
                        platform_fee_share=platform_fee_share,
                        total_transfer_amount=transfer_amount,
                        # transfer_id=transfer.id,
                        # transfer_status='completed'
                        transfer_id=transfer_id,
                        transfer_status=transfer_status
                    )
                    
                    # ✅ Create RetailerOrder for each product
                    for product_data in data['products']:
                        RetailerOrder.objects.create(
                            payment=payment,
                            retailer=retailer,
                            product=product_data['product_obj'],
                            product_name=product_data['name'],
                            quantity=product_data['quantity'],
                            unit_price=product_data['price'],
                            total_amount=product_data['total'],
                            delivery_address_label=delivery_address.address_label,
                            delivery_full_address=delivery_address.full_address,
                            delivery_area=delivery_address.area,
                            delivery_postal_code=delivery_address.postal_code,
                            delivery_phone=delivery_address.phone_number,
                            status='pending'
                        )
                    
                    # ✅ Update retailer stats
                    retailer.total_orders += len(data['products'])
                    retailer.total_sales += subtotal
                    retailer.total_pending += subtotal
                    retailer.save(update_fields=['total_orders', 'total_sales', 'total_pending'])


                except stripe.error.StripeError as e:
                    # Log error
                    PaymentRetailerSplit.objects.create(
                        payment=payment,
                        retailer=retailer,
                        product_amount=product_amount,
                        delivery_share=delivery_share,
                        platform_fee_share=platform_fee_share,
                        total_transfer_amount=transfer_amount,
                        transfer_status='failed'
                    )

            return self.success_response(
                data={
                    'checkout_url': session.url,
                    'session_id': session.id,
                    'payment_id': payment.id,
                    'products': response_products,  # ✅ NEW
                    'delivery_address': {
                        'id': delivery_address.id,
                        'address_label': delivery_address.address_label,
                        'full_address': delivery_address.full_address
                    },
                    'summary': {
                        'subtotal': str(total_amount),
                        'delivery_charge': str(total_delivery),
                        'total': str(final_total)
                    }
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

'''
@transaction.atomic
def handle_successful_payment(session):
    payment_id = session['metadata']['payment_id']
    payment = Payment.objects.get(id=payment_id)
    
    # ✅ NOW set payment_intent_id (from Stripe's response)
    payment.payment_intent_id = session['payment_intent']
    payment.status = 'completed'
    #payment.save()
    payment.save(update_fields=['payment_intent_id', 'status'])
    
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
            ## ✅ Create Stripe Transfer (NOT in checkout, in webhook)
            transfer = stripe.Transfer.create(
                amount=int(transfer_amount * 100),
                currency='gbp',
                destination=retailer.stripe_account_id,
                transfer_group=payment.payment_intent_id,
                metadata={
                    'payment_id': payment.id,
                    'retailer_id': retailer.id
                }
            )
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

'''


@transaction.atomic
def handle_successful_payment(session):
    """Process successful payment and split to retailers"""
    
    payment_id = session['metadata']['payment_id']
    product_ids = session['metadata'].get('product_ids', '').split(',')
    payment = Payment.objects.get(id=payment_id)
    
    # ✅ NOW set payment_intent_id (from Stripe's response)
    payment.payment_intent_id = session['payment_intent']
    payment.status = 'completed'
    #payment.save()
    payment.save(update_fields=['payment_intent_id', 'status'])
    
    
    #==================================
        # ✅ Fetch products (replace cart query)
    from mixapp.models import ShopProduct
    from django.db.models import F
    from paymentapp.models import RetailerOrder  # ✅ ADD THIS

    products = ShopProduct.objects.filter(
        id__in=[int(pid) for pid in product_ids if pid]
    ).select_related('retailer')
    
    # ✅ Get quantities from line items
    line_items = stripe.checkout.Session.list_line_items(session['id'])
    quantity_map = {}
    for item in line_items.data:
        if 'Delivery' not in item.description:
            # Match by price to get product
            for product in products:
                if int(product.market_price * 100) == item.price.unit_amount:
                    quantity_map[product.id] = item.quantity
                    break
    
    #================================================\
    # ✅ NEW: Decrease product quantities
    for product in products:
        quantity_sold = quantity_map.get(product.id, 0)
        if quantity_sold > 0:
            # Update quantity atomically (prevents race conditions)
            ShopProduct.objects.filter(id=product.id).update(
                quantity=F('quantity') - quantity_sold
            )
            
            ## ✅ CRITICAL: Refresh from DB to get updated quantity
    #product.refresh_from_db()
    # ✅ NEW: Refresh ALL products from DB after quantity updates
    products = ShopProduct.objects.filter(
        id__in=[int(pid) for pid in product_ids if pid]
    ).select_related('retailer')

    # ✅ NOW loop through FRESH products and update stock_status
    for product in products:
        if product.quantity <= 0:
            product.stock_status = 'out_of_stock'
        elif product.quantity <= 10:
            product.stock_status = 'low_stock'
        else:
            product.stock_status = 'in_stock'
        
        product.save(update_fields=['stock_status'])

    #================================================/
    # ✅ Rest of the logic remains same (retailer splits)
    retailer_totals = {}
    total_amount = Decimal('0.00')
    
    for product in products:
        retailer = product.retailer
        quantity = quantity_map.get(product.id, 1)
        product_total = product.market_price * quantity
        
        if retailer.id not in retailer_totals:
            retailer_totals[retailer.id] = {
                'retailer': retailer,
                'product_amount': Decimal('0.00'),
                'delivery_charge': retailer.delivery_charge,
                'products': []  # ✅ ADD THIS
            }
        
        retailer_totals[retailer.id]['product_amount'] += product_total

        retailer_totals[retailer.id]['products'].append({  # ✅ ADD THIS
            'product': product,
            'quantity': quantity,
            'unit_price': product.market_price,
            'total': product_total
        })
        
        total_amount += product_total
    
    
    
    #=====================================
    # Get cart items grouped by retailer
    '''
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
    '''
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

        transfer_id = None
        transfer_status = 'pending'
        try:
            ## ✅ Create Stripe Transfer (NOT in checkout, in webhook)
            transfer = stripe.Transfer.create(
                amount=int(transfer_amount * 100),
                currency='gbp',
                destination=retailer.stripe_account_id,
                transfer_group=payment.payment_intent_id,
                metadata={
                    'payment_id': payment.id,
                    'retailer_id': retailer.id
                }
            )
            transfer_id = None
            transfer_status = 'pending'
        except stripe.error.StripeError as e:
            # Log error but continue with other transfers
            transfer_status = 'failed'
            print(f"Webhook: Transfer failed for retailer {retailer.id}: {str(e)}")

            # Record split
            PaymentRetailerSplit.objects.create(
                payment=payment,
                retailer=retailer,
                product_amount=product_amount,
                delivery_share=delivery_share,
                platform_fee_share=platform_fee_share,
                total_transfer_amount=transfer_amount,
                # transfer_id=transfer.id,
                # transfer_status='completed'
                transfer_id=transfer_id,
                transfer_status=transfer_status
            )
            # ✅ NEW: Create RetailerOrder for each product
            for product_data in data['products']:
                RetailerOrder.objects.create(
                    payment=payment,
                    retailer=retailer,
                    product=product_data['product'],
                    product_name=product_data['product'].name,
                    quantity=product_data['quantity'],
                    unit_price=product_data['unit_price'],
                    total_amount=product_data['total'],
                    delivery_address_label=payment.delivery_address.address_label,
                    delivery_full_address=payment.delivery_address.full_address,
                    delivery_area=payment.delivery_address.area,
                    delivery_postal_code=payment.delivery_address.postal_code,
                    delivery_phone=payment.delivery_address.phone_number,
                    status='pending'
                )
            
            # ✅ NEW: Update retailer stats
            retailer.total_orders += len(data['products'])
            retailer.total_sales += subtotal
            retailer.total_pending += subtotal
            retailer.save(update_fields=['total_orders', 'total_sales', 'total_pending'])
        # except stripe.error.StripeError as e:
        #     # Log error but continue with other transfers
        #     PaymentRetailerSplit.objects.create(
        #         payment=payment,
        #         retailer=retailer,
        #         product_amount=product_amount,
        #         delivery_share=delivery_share,
        #         platform_fee_share=platform_fee_share,
        #         total_transfer_amount=transfer_amount,
        #         transfer_status='failed'
        #     )
    
    # Clear cart
    # cart_items.delete()

# Add these imports at top
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

# Add these views

def payment_success_view(request):
    """Render success page after payment"""
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return render(request, 'paymentapp/cancel.html')
    
    try:
        # Retrieve session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Get payment record
        #payment_id = session['metadata'].get('payment_id') #❌❌❌
        #❌❌Stripe's Python SDK returns objects, not plain dicts. session['metadata'] is a StripeObject, not a regular Python dict, so .get() doesn't work on it.

        payment_id = session.metadata['payment_id']
        '''
        The root rule: never call .get() directly on any Stripe object — session, session.metadata, session.payment_method_details are all StripeObject instances, not Python dicts. Use either object.attribute or object['key'] syntax instead.

        '''
        payment = Payment.objects.get(id=payment_id)
        
        # Get card details (if available)
        card_last4 = '****'
        # if session.get('payment_method_details'):
        #     card_last4 = session['payment_method_details'].get('card', {}).get('last4', '****')
        '''
        # ✅ Fix 2: card details aren't on Session object at all
        # Use payment_intent instead to get card info
        '''

        try:
            if session.payment_intent:
                intent = stripe.PaymentIntent.retrieve(
                    session.payment_intent,
                    expand=['payment_method']
                )
                card_last4 = intent.payment_method.card.last4 or '****'
        except Exception:
            pass  # card_last4 stays as '****', not critical

        context = {
            'session_id': session_id,
            'payment_id': payment.id,
            'total_amount': payment.total_amount,
            'card_last4': card_last4,
            'status': payment.status
        }
        
        return render(request, 'paymentapp/success.html', context)
    
    # except (stripe.error.StripeError, Payment.DoesNotExist):
    #     return render(request, 'paymentapp/cancel.html')
    except Exception as e:
        import traceback
        traceback.print_exc()  # ✅ Shows the REAL error in terminal
        return render(request, 'paymentapp/cancel.html')

def payment_cancel_view(request):
    """Render cancel page when payment is cancelled"""
    return render(request, 'paymentapp/cancel.html')


#======================================================================================================
#Retailer sales 

# retailerapp/views.py

'''
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from paymentapp.models import PaymentRetailerSplit
from paymentapp.serializers import MonthlySalesSerializer


class RetailerMonthlySalesView(StandardResponseMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        if user.role != 'retailer' or not hasattr(user, 'retailer_profile'):
            return self.error_response("Unauthorized - retailer access only", status_code=403)

        retailer = user.retailer_profile

        years_back = int(request.query_params.get('years', 1))

        end_date = datetime.now().date()
        start_date = end_date - relativedelta(years=years_back)

        queryset = (
            PaymentRetailerSplit.objects
            .filter(
                retailer=retailer,
                payment__status='pending', # will change it to payment status 'complete' later at production
                payment__created_at__date__gte=start_date,
                payment__created_at__date__lte=end_date
            )
            .annotate(month=TruncMonth('payment__created_at'))
            .values('month')
            .annotate(
                total_sales=Sum('product_amount'),
                order_count=Count('payment', distinct=True)
            )
        )

        # Convert queryset to dictionary
        sales_map = {}

        for row in queryset:
            key = row['month'].strftime("%Y-%m")
            sales_map[key] = row

        # Generate full month list
        result = []

        current = start_date.replace(day=1)

        while current <= end_date:

            key = current.strftime("%Y-%m")

            row = sales_map.get(key)

            total_sales = row['total_sales'] if row else Decimal('0.00')
            order_count = row['order_count'] if row else 0

            result.append({
                "year": current.year,
                "month_index": current.month - 1,   # Jan=0
                "month_name": current.strftime("%B"),
                "total_sales": total_sales,
                "order_count": order_count
            })

            current += relativedelta(months=1)

        serializer = MonthlySalesSerializer(result, many=True)

        lifetime_total = PaymentRetailerSplit.objects.filter(
            retailer=retailer,
            payment__status='completed'
        ).aggregate(total=Sum('product_amount'))['total'] or Decimal('0.00')

        return self.success_response(
            data={
                "monthly_sales": serializer.data,
                "lifetime_total_sales": str(lifetime_total),
                "currency": "GBP"
            },
            message="Monthly sales retrieved successfully",
            status_code=200
        )


'''


from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth
from decimal import Decimal
import calendar

from paymentapp.models import PaymentRetailerSplit
from paymentapp.serializers import SalesChartSerializer


class RetailerMonthlySalesChartView(StandardResponseMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        if user.role != "retailer" or not hasattr(user, "retailer_profile"):
            return self.error_response("Unauthorized", status_code=403)

        retailer = user.retailer_profile
        from datetime import datetime
        #year = int(request.query_params.get("year"))
        year = int(request.query_params.get("year", datetime.now().year))

        queryset = (
            PaymentRetailerSplit.objects
            .filter(
                retailer=retailer,
                payment__status="pending",
                payment__created_at__year=year
            )
            .annotate(month=ExtractMonth("payment__created_at"))
            .values("month")
            .annotate(
                sales=Sum("product_amount"),
                orders=Count("payment", distinct=True)
            )
        )

        data_map = {row["month"]: row for row in queryset}

        labels = []
        sales = []
        orders = []

        for m in range(1, 13):

            labels.append(calendar.month_abbr[m])

            row = data_map.get(m)

            sales.append(row["sales"] if row else Decimal("0.00"))
            orders.append(row["orders"] if row else 0)

        response_data = {
            "labels": labels,
            "sales": sales,
            "orders": orders
        }

        serializer = SalesChartSerializer(response_data)

        return self.success_response(
            data=serializer.data,
            message="Monthly sales chart retrieved of a specific year",
            status_code=200
        )


from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from .models import RetailerOrder
from .serializers import UserOrderSerializer

class MyOrdersView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserOrderSerializer

    def get_queryset(self):
        return RetailerOrder.objects.filter(
            payment__user=self.request.user
        ).select_related('retailer', 'payment').order_by('-created_at')








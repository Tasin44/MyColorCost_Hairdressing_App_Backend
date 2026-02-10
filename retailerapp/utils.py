import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def is_stripe_supported_country(country_code):
    """Check if country supports Stripe Connect"""
    try:
        stripe.CountrySpec.retrieve(country_code)
        return True
    except stripe.error.InvalidRequestError:
        return False


def is_stripe_onboarding_complete(account_id):
    """Verify if Stripe onboarding is fully complete"""
    try:
        account = stripe.Account.retrieve(account_id)
        return account.charges_enabled and account.details_submitted
    except Exception:
        return False
# mixapp/new_views.py
#
# NEW views only — existing mixapp/views.py is untouched.
#

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from .models import Mix, Bowl, BowlProduct
from clientapp.models import Client
from .new_serializers import (
    NewMixCreateSerializer,
    NewMixListSerializer,
    NewMixDetailSerializer,
)

import logging
logger = logging.getLogger(__name__)


class NewStandardResponseMixin:
    """Consistent API response format."""

    def success_response(self, data=None, message="Success", status_code=200):
        return Response({
            "success": True,
            "statusCode": status_code,
            "message": message,
            "data": data,
        }, status=status_code)

    def error_response(self, message, status_code=400, data=None):
        return Response({
            "success": False,
            "statusCode": status_code,
            "message": message,
            "data": data,
        }, status=status_code)

    def serializer_error_response(self, errors, status_code=400):
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


# ===========================================================================
# New Mix Create + List
# ===========================================================================

class NewMixView(NewStandardResponseMixin, APIView):
    """
    GET  /mix/mixes/new/   → List all mixes (owner sees all; staff sees own)
    POST /mix/mixes/new/   → Create a new mix with bowls

    POST body:
    {
        "client_id": 5,
        "service_type": "2",          // ServiceType ID or name
        "bowls": [
            {
                "service_name": "Hair Color",
                "mix_name": "Spa mix14",
                "charged_amount": 400,
                "bleach_timer_start_time": "2024-01-23T10:30:00",
                "products": [
                    {
                        "user_product_id": 26,
                        "used_weight": 5,
                        "user_price": 200,
                        "market_price": 200
                    }
                ]
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def _get_owner_and_sub(self, user):
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            return user.staff_profile.main_user, user.staff_profile
        return user, None

    def get(self, request):
        """List all mixes in new format (with bowls)."""
        user = request.user
        owner, sub_user = self._get_owner_and_sub(user)

        queryset = Mix.objects.filter(user=owner).select_related(
            'client', 'user', 'sub_user', 'service_type_fk'
        ).prefetch_related('bowls__bowl_products')

        # Staff sees only their own mixes
        if sub_user:
            queryset = queryset.filter(sub_user=sub_user)

        # Optional filters
        client_id = request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        service_type = request.query_params.get('service_type', '').strip()
        if service_type:
            queryset = queryset.filter(
                Q(service_type__iexact=service_type) |
                Q(service_type_fk__name__iexact=service_type)
            )

        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        if from_date:
            queryset = queryset.filter(created_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_at__date__lte=to_date)

        queryset = queryset.order_by('-created_date', '-created_time')

        serializer = NewMixListSerializer(queryset, many=True, context={'request': request})
        return self.success_response(
            data={
                'mixes': serializer.data,
                'total_count': queryset.count(),
            },
            message="Mixes retrieved successfully.",
        )

    @transaction.atomic
    def post(self, request):
        """Create a new mix with bowls."""
        user = request.user
        if user.role not in ['owner', 'staff', 'self_employed']:
            return self.error_response(
                "You don't have permission to create mixes.",
                status_code=403,
            )

        serializer = NewMixCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        try:
            mix = serializer.save()
        except Exception as e:
            logger.exception(f"Error creating mix: {e}")
            return self.error_response(f"Server error: {str(e)}", status_code=500)

        return self.success_response(
            data=NewMixDetailSerializer(mix, context={'request': request}).data,
            message="Mix created successfully.",
            status_code=201,
        )


class NewMixDetailView(NewStandardResponseMixin, APIView):
    """
    GET /mix/mixes/<mix_id>/new/  → Retrieve a single mix with full bowl detail
    """
    permission_classes = [IsAuthenticated]

    def _get_mix(self, request, mix_id):
        user = request.user
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            sub_user = user.staff_profile
            try:
                return Mix.objects.select_related(
                    'client', 'user', 'sub_user', 'service_type_fk'
                ).prefetch_related(
                    'bowls__bowl_products__user_product__product'
                ).get(id=mix_id, user=owner, sub_user=sub_user)
            except Mix.DoesNotExist:
                return None
        else:
            try:
                return Mix.objects.select_related(
                    'client', 'user', 'sub_user', 'service_type_fk'
                ).prefetch_related(
                    'bowls__bowl_products__user_product__product'
                ).get(id=mix_id, user=user)
            except Mix.DoesNotExist:
                return None

    def get(self, request, mix_id):
        mix = self._get_mix(request, mix_id)
        if not mix:
            return self.error_response("Mix not found.", status_code=404)
        return self.success_response(
            data=NewMixDetailSerializer(mix, context={'request': request}).data,
            message="Mix retrieved successfully.",
        )

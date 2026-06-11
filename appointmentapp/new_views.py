# appointmentapp/new_views.py
#
# NEW views only — existing views.py is untouched.
#

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    DailyWorkingHours, ServiceType, AppointmentURL,
    Appointment, TimeSlotBooking,
)
from .new_serializers import (
    ServiceTypeCreateSerializer,
    ServiceTypeDetailSerializer,
    NewWorkingHoursSetupSerializer,
    DailyWorkingHoursSerializer,
    NewAppointmentCreateSerializer,
    NewAppointmentDetailSerializer,
    NewSelfBookingSerializer,
)

import logging
logger = logging.getLogger(__name__)


class NewStandardResponseMixin:
    """Consistent API response format (mirrors existing mixin)."""

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
# 1. SERVICE MANAGEMENT  (Settings → Services)
# ===========================================================================

class ServiceListView(NewStandardResponseMixin, APIView):
    """
    GET  /appointment/services/   → list all services for authenticated user
    POST /appointment/services/   → create a new service
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all services belonging to the requesting user (or their owner)."""
        import secrets
        user = request.user

        # Staff sees their owner's services
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
            
        # Get or create appointment URL for the owner
        appointment_url, created = AppointmentURL.objects.get_or_create(
            user=owner,
            defaults={'token': secrets.token_urlsafe(16)}
        )

        services = ServiceType.objects.filter(user=owner).order_by('name')
        serializer = ServiceTypeDetailSerializer(services, many=True)
        return self.success_response(
            data={
                'token': appointment_url.token,
                'booking_url': f"{appointment_url.booking_url}new",
                'services': serializer.data,
                'total_count': services.count(),
            },
            message="Services retrieved successfully",
        )

    @transaction.atomic
    def post(self, request):
        """Create a new service."""
        user = request.user
        if user.role not in ['owner', 'self_employed']:
            return self.error_response(
                "Only owners and self-employed users can manage services.",
                status_code=403,
            )

        serializer = ServiceTypeCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        if serializer.is_valid():
            service = serializer.save()
            return self.success_response(
                data=ServiceTypeDetailSerializer(service).data,
                message="Service created successfully.",
                status_code=201,
            )
        return self.serializer_error_response(serializer.errors)


class ServiceDetailView(NewStandardResponseMixin, APIView):
    """
    GET    /appointment/services/<id>/   → get service detail
    PATCH  /appointment/services/<id>/   → update service
    DELETE /appointment/services/<id>/   → remove service
    """
    permission_classes = [IsAuthenticated]

    def _get_owner(self, user):
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            return user.staff_profile.main_user
        return user

    def _get_service(self, user, service_id):
        owner = self._get_owner(user)
        try:
            return ServiceType.objects.get(id=service_id, user=owner)
        except ServiceType.DoesNotExist:
            return None

    def get(self, request, service_id):
        service = self._get_service(request.user, service_id)
        if not service:
            return self.error_response("Service not found.", status_code=404)
        return self.success_response(
            data=ServiceTypeDetailSerializer(service).data,
            message="Service retrieved successfully.",
        )

    @transaction.atomic
    def patch(self, request, service_id):
        user = request.user
        if user.role not in ['owner', 'self_employed']:
            return self.error_response(
                "Only owners and self-employed users can manage services.",
                status_code=403,
            )
        service = self._get_service(user, service_id)
        if not service:
            return self.error_response("Service not found.", status_code=404)

        serializer = ServiceTypeCreateSerializer(
            service,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if serializer.is_valid():
            service = serializer.save()
            return self.success_response(
                data=ServiceTypeDetailSerializer(service).data,
                message="Service updated successfully.",
            )
        return self.serializer_error_response(serializer.errors)

    @transaction.atomic
    def delete(self, request, service_id):
        user = request.user
        if user.role not in ['owner', 'self_employed']:
            return self.error_response(
                "Only owners and self-employed users can manage services.",
                status_code=403,
            )
        service = self._get_service(user, service_id)
        if not service:
            return self.error_response("Service not found.", status_code=404)

        name = service.name
        service.delete()
        return self.success_response(
            message=f"Service '{name}' deleted successfully.",
        )


# ===========================================================================
# 2. PER-DAY WORKING HOURS SETUP
# ===========================================================================

class NewWorkingHoursSetupView(NewStandardResponseMixin, APIView):
    """
    POST  /appointment/working-hours/setup/new/  → bulk create / update per-day hours
    GET   /appointment/working-hours/setup/new/  → retrieve current per-day hours
    PATCH /appointment/working-hours/setup/new/  → update one or more specific days

    Body for POST / PATCH:
    {
        "days": [
            {"weekday": 0, "start_time": "09:00", "end_time": "20:00", "is_off": false},
            {"weekday": 6, "is_off": true}
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def _get_owner(self, user):
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            return user.staff_profile.main_user
        return user

    def get(self, request):
        """Return all per-day working hours for this user."""
        owner = self._get_owner(request.user)
        entries = DailyWorkingHours.objects.filter(user=owner).order_by('weekday')
        serializer = DailyWorkingHoursSerializer(entries, many=True)

        # Also include off_days list for convenience
        off_days = list(
            entries.filter(is_off=True).values_list('weekday', flat=True)
        )

        return self.success_response(
            data={
                'id': owner.id,
                'is_locked': False,  # always editable in new flow
                'working_days': serializer.data,
                'off_days': off_days,
                'created_at': entries.first().created_at if entries.exists() else None,
            },
            message="Working hours retrieved successfully.",
        )

    @transaction.atomic
    def post(self, request):
        """Bulk-create or upsert per-day working hours."""
        user = request.user
        if user.role not in ['owner', 'self_employed']:
            return self.error_response(
                "Only owners and self-employed users can configure working hours.",
                status_code=403,
            )

        owner = self._get_owner(user)
        serializer = NewWorkingHoursSetupSerializer(data=request.data)
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        results = serializer.create_or_update(owner)
        all_entries = DailyWorkingHours.objects.filter(user=owner).order_by('weekday')
        off_days = list(all_entries.filter(is_off=True).values_list('weekday', flat=True))

        return self.success_response(
            data={
                'id': owner.id,
                'is_locked': True,
                'working_days': DailyWorkingHoursSerializer(all_entries, many=True).data,
                'off_days': off_days,
                'created_at': results[0].created_at if results else None,
            },
            message="Working hours set successfully.",
            status_code=201,
        )

    @transaction.atomic
    def patch(self, request):
        """Update one or more days (same body structure as POST)."""
        user = request.user
        if user.role not in ['owner', 'self_employed']:
            return self.error_response(
                "Only owners and self-employed users can configure working hours.",
                status_code=403,
            )

        owner = self._get_owner(user)
        serializer = NewWorkingHoursSetupSerializer(data=request.data)
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        results = serializer.create_or_update(owner)
        all_entries = DailyWorkingHours.objects.filter(user=owner).order_by('weekday')
        off_days = list(all_entries.filter(is_off=True).values_list('weekday', flat=True))

        return self.success_response(
            data={
                'id': owner.id,
                'is_locked': True,
                'working_days': DailyWorkingHoursSerializer(all_entries, many=True).data,
                'off_days': off_days,
            },
            message="Working hours updated successfully.",
        )


# ===========================================================================
# 3. NEW APPOINTMENT CREATION (manual — owner / staff)
# ===========================================================================

class NewAppointmentCreateView(NewStandardResponseMixin, APIView):
    """
    POST /appointment/create/new/

    Body:
    {
        "client_id": 11,
        "appointment_date": "2026-02-10",
        "appointment_time": "10:00",
        "service_type_ids": [5, 7],          // list of service IDs (optional)
        "service_name": "Haircut",            // free text fallback (optional)
        "reminder_hours": 2,                  // optional
        "notes": "...",                       // optional
        "processing_time": 10,               // optional 1-60
        "blocked_time": 5,                   // optional 1-60
        "extra_servicing": 15               // optional 1-60
    }
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        if user.role not in ['owner', 'staff', 'self_employed']:
            return self.error_response(
                "You don't have permission to create appointments.",
                status_code=403,
            )

        serializer = NewAppointmentCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        appointment = serializer.save()
        return self.success_response(
            data=NewAppointmentDetailSerializer(
                appointment, context={'request': request}
            ).data,
            message="Appointment created successfully.",
            status_code=201,
        )


# ===========================================================================
# 4. NEW CLIENT SELF-BOOKING
# ===========================================================================

class NewSelfBookingView(NewStandardResponseMixin, APIView):
    """
    GET  /appointment/book/<token>/new/  → return salon info + enriched services
    POST /appointment/book/<token>/new/  → client books an appointment
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        """Return booking page info with full service details."""
        try:
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=token, is_active=True
            )
        except AppointmentURL.DoesNotExist:
            return self.error_response(
                "Invalid or inactive booking URL.", status_code=404
            )

        owner = appointment_url.user

        # Build working hours data (prefer new DailyWorkingHours)
        daily_entries = DailyWorkingHours.objects.filter(user=owner).order_by('weekday')
        if daily_entries.exists():
            working_hours_data = {
                'type': 'per_day',
                'days': DailyWorkingHoursSerializer(daily_entries, many=True).data,
                'off_days': list(
                    daily_entries.filter(is_off=True).values_list('weekday', flat=True)
                ),
            }
        elif hasattr(owner, 'working_hours'):
            wh = owner.working_hours
            working_hours_data = {
                'type': 'global',
                'start_time': wh.start_time.strftime('%H:%M'),
                'end_time': wh.end_time.strftime('%H:%M'),
                'off_days': wh.get_off_days_list(),
            }
        else:
            return self.error_response(
                "Booking unavailable — working hours not configured.", status_code=400
            )

        services = ServiceType.objects.filter(user=owner)
        return self.success_response(
            data={
                'salon_name': owner.name or owner.email,
                'user_id': str(owner.id),
                'services': ServiceTypeDetailSerializer(services, many=True).data,
                'working_hours': working_hours_data,
            },
            message="Booking information retrieved successfully.",
        )

    @transaction.atomic
    def post(self, request, token):
        """Client self-booking."""
        serializer = NewSelfBookingSerializer(
            data=request.data,
            context={'request': request, 'token': token},
        )
        if not serializer.is_valid():
            return self.serializer_error_response(serializer.errors)

        try:
            appointment = serializer.save()
        except Exception as e:
            logger.exception(f"Error saving self-booked appointment: {e}")
            return self.error_response(f"Server error: {str(e)}", status_code=500)

        return self.success_response(
            data=NewAppointmentDetailSerializer(
                appointment, context={'request': request}
            ).data,
            message="Appointment booked successfully! Confirmation email sent.",
            status_code=201,
        )


# ===========================================================================
# 5. AVAILABLE TIME SLOTS (new version aware of DailyWorkingHours)
# ===========================================================================

class NewAvailableTimeSlotsView(NewStandardResponseMixin, APIView):
    """
    GET /appointment/available-slots/new/?date=YYYY-MM-DD[&user_id=xxx]

    Uses DailyWorkingHours if configured, falls back to WorkingHours.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        date_str = request.query_params.get('date')
        user_id = request.query_params.get('user_id')

        if not date_str:
            return self.error_response("date parameter is required.", status_code=400)

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return self.error_response(
                "Invalid date format. Use YYYY-MM-DD.", status_code=400
            )

        if date < timezone.now().date():
            return self.error_response(
                "Cannot check availability for past dates.", status_code=400
            )

        # Resolve owner
        if user_id:
            from authapp.models import User
            try:
                owner = User.objects.get(id=user_id, role='owner')
            except User.DoesNotExist:
                return self.error_response("Invalid user.", status_code=404)
        else:
            if not request.user.is_authenticated:
                return self.error_response("Authentication required.", status_code=401)
            user = request.user
            if user.role == 'staff' and hasattr(user, 'staff_profile'):
                owner = user.staff_profile.main_user
            else:
                owner = user

        # Try new DailyWorkingHours first
        day_entry = DailyWorkingHours.objects.filter(
            user=owner, weekday=date.weekday()
        ).first()

        if day_entry:
            if day_entry.is_off:
                return self.success_response(
                    data={'date': date, 'is_working_day': False, 'available_slots': []},
                    message="Selected date is an off day.",
                )
            all_slots = day_entry.generate_time_slots()
            start_time = day_entry.start_time
            end_time = day_entry.end_time
        elif hasattr(owner, 'working_hours'):
            wh = owner.working_hours
            if not wh.is_working_day(date):
                return self.success_response(
                    data={'date': date, 'is_working_day': False, 'available_slots': []},
                    message="Selected date is an off day.",
                )
            all_slots = wh.generate_time_slots()
            start_time = wh.start_time
            end_time = wh.end_time
        else:
            return self.error_response("Working hours not configured.", status_code=404)

        # Get existing bookings
        existing = TimeSlotBooking.objects.filter(user=owner, date=date)
        booking_lookup = {b.time_slot: b for b in existing}

        max_capacity = owner.staff_limit if (owner.role == 'owner' and owner.staff_limit > 0) else 1

        duration_str = request.query_params.get('duration')
        duration = 0
        if duration_str:
            try:
                duration = int(duration_str)
            except ValueError:
                pass

        slots_capacity = {}
        for slot in all_slots:
            booking = booking_lookup.get(slot)
            current = booking.current_bookings if booking else 0
            slots_capacity[slot] = max_capacity - current

        available_slots = []
        for slot in all_slots:
            is_slot_available = True
            
            if duration > 0:
                intervals = (duration + 14) // 15
                current_time = datetime.combine(date, slot)
                for i in range(intervals):
                    check_time = (current_time + timedelta(minutes=15 * i)).time()
                    if check_time not in slots_capacity or slots_capacity[check_time] <= 0:
                        is_slot_available = False
                        break
            else:
                is_slot_available = slots_capacity[slot] > 0

            available_slots.append({
                'time_slot': slot.strftime('%H:%M'),
                'available_capacity': slots_capacity[slot],
                'max_capacity': max_capacity,
                'is_available': is_slot_available,
            })

        return self.success_response(
            data={
                'date': date,
                'is_working_day': True,
                'working_hours': {
                    'start_time': start_time.strftime('%H:%M'),
                    'end_time': end_time.strftime('%H:%M'),
                },
                'available_slots': available_slots,
            },
            message="Available slots retrieved successfully.",
        )


class NewBookingPageView(APIView):
    """
    Render HTML booking page for clients (no auth required).
    This just serves the HTML template. The JavaScript in the template
    will fetch booking data from NewSelfBookingView.get()
    """
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        """Render booking page HTML template"""
        from django.shortcuts import render
        try:
            # Verify token exists and is active
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=token,
                is_active=True
            )
            
            return render(
                request, 
                'appointmentapp/new_booking_page.html',
                {'token': token}
            )
            
        except AppointmentURL.DoesNotExist:
            return render(
                request,
                'appointmentapp/invalid_link.html',
                {'message': 'Invalid or expired booking link'},
                status=404
            )

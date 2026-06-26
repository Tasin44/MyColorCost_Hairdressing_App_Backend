# appointmentapp/new_serializers.py
#
# NEW serializers only — existing serializers.py is untouched.
#

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import secrets

from .models import (
    DailyWorkingHours, ServiceType, AppointmentURL,
    Appointment, TimeSlotBooking
)
from clientapp.models import Client
from authapp.models import User
from django.conf import settings


# ===========================================================================
# 1. SERVICE MANAGEMENT
# ===========================================================================

class ServiceTypeCreateSerializer(serializers.ModelSerializer):
    """
    Create / update a service in the settings.
    POST  /appointment/services/
    PATCH /appointment/services/<id>/
    """

    class Meta:
        model = ServiceType
        fields = [
            'id', 'name', 'description',
            'service_time_minutes', 'price_type', 'service_fee',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Service name cannot be blank.")
        return value.strip()

    def validate(self, data):
        user = self.context['request'].user
        name = data.get('name', '').strip()

        # On create check unique_together
        if not self.instance:
            if ServiceType.objects.filter(user=user, name__iexact=name).exists():
                raise serializers.ValidationError(
                    {"name": "You already have a service with this name."}
                )

        # On update check unique_together (excluding self)
        if self.instance:
            qs = ServiceType.objects.filter(user=user, name__iexact=name)
            if qs.exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError(
                    {"name": "You already have a service with this name."}
                )

        # price_type=free → fee must be 0 / null
        price_type = data.get('price_type', getattr(self.instance, 'price_type', 'fixed'))
        if price_type == 'free':
            data['service_fee'] = None

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        return ServiceType.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ServiceTypeDetailSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for a single service — returned by GET.
    """
    price_type_display = serializers.CharField(
        source='get_price_type_display', read_only=True
    )

    class Meta:
        model = ServiceType
        fields = [
            'id', 'name', 'description',
            'service_time_minutes', 'price_type', 'price_type_display',
            'service_fee', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


# ===========================================================================
# 2. PER-DAY WORKING HOURS
# ===========================================================================

class DailyWorkingHoursSerializer(serializers.ModelSerializer):
    """Single-day working hours entry (used nested in bulk setup)."""

    weekday_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyWorkingHours
        fields = [
            'id', 'weekday', 'weekday_name',
            'start_time', 'end_time', 'is_off',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'weekday_name', 'created_at', 'updated_at']

    def get_weekday_name(self, obj):
        days = ['Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[obj.weekday] if 0 <= obj.weekday <= 6 else str(obj.weekday)

    def validate(self, data):
        is_off = data.get('is_off', getattr(self.instance, 'is_off', False))
        start = data.get('start_time', getattr(self.instance, 'start_time', None))
        end = data.get('end_time', getattr(self.instance, 'end_time', None))

        if not is_off:
            if not start or not end:
                raise serializers.ValidationError(
                    "start_time and end_time are required for working days."
                )
            if start >= end:
                raise serializers.ValidationError(
                    "end_time must be after start_time."
                )
        return data


class NewWorkingHoursSetupSerializer(serializers.Serializer):
    """
    Bulk setup / update of per-day working hours.
    POST  /appointment/working-hours/setup/new/   → create all 7 days at once
    PATCH /appointment/working-hours/setup/new/   → update one or more days

    Expected body:
    {
        "days": [
            {"weekday": 0, "start_time": "09:00", "end_time": "20:00", "is_off": false},
            {"weekday": 6, "is_off": true},
            ...
        ]
    }
    """
    days = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
    )

    def validate_days(self, days_data):
        validated = []
        weekdays_seen = set()

        for entry in days_data:
            weekday = entry.get('weekday')
            if weekday is None or not isinstance(weekday, int) or weekday < 0 or weekday > 6:
                raise serializers.ValidationError(
                    f"Each entry must have a valid weekday (0-6). Got: {weekday}"
                )
            if weekday in weekdays_seen:
                raise serializers.ValidationError(
                    f"Duplicate weekday {weekday} in request."
                )
            weekdays_seen.add(weekday)

            is_off = entry.get('is_off', False)
            start_time = entry.get('start_time')
            end_time = entry.get('end_time')

            if not is_off:
                if not start_time or not end_time:
                    raise serializers.ValidationError(
                        f"weekday {weekday}: start_time and end_time are required."
                    )
                # Parse times
                try:
                    st = datetime.strptime(start_time, '%H:%M').time()
                    et = datetime.strptime(end_time, '%H:%M').time()
                except ValueError:
                    raise serializers.ValidationError(
                        f"weekday {weekday}: time must be HH:MM format."
                    )
                if st >= et:
                    raise serializers.ValidationError(
                        f"weekday {weekday}: end_time must be after start_time."
                    )
                validated.append({
                    'weekday': weekday,
                    'start_time': st,
                    'end_time': et,
                    'is_off': False,
                })
            else:
                validated.append({
                    'weekday': weekday,
                    'start_time': None,
                    'end_time': None,
                    'is_off': True,
                })

        return validated

    @transaction.atomic
    def create_or_update(self, user):
        """Upsert each day for the user. Returns list of DailyWorkingHours."""
        days_data = self.validated_data['days']
        results = []
        for day in days_data:
            obj, _ = DailyWorkingHours.objects.update_or_create(
                user=user,
                weekday=day['weekday'],
                defaults={
                    'start_time': day['start_time'],
                    'end_time': day['end_time'],
                    'is_off': day['is_off'],
                }
            )
            results.append(obj)
        return results


# ===========================================================================
# 3. NEW APPOINTMENT CREATION (manual by owner/staff)
# ===========================================================================

class NewAppointmentCreateSerializer(serializers.Serializer):
    """
    POST /appointment/create/new/
    Supports multiple service_type IDs and optional extra times.
    """
    client_id = serializers.IntegerField()
    appointment_date = serializers.DateField()
    appointment_time = serializers.TimeField()

    # Multiple services: list of ServiceType IDs
    service_type_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="List of ServiceType IDs from your service list"
    )
    service_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Free-text service name (used if no service_type_ids)"
    )
    reminder_hours = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default=''
    )
    # Extra times (optional, 1-60 min each)
    processing_time = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=60
    )
    blocked_time = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=60
    )
    extra_servicing = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=60
    )

    def _get_owner(self, user):
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            return user.staff_profile.main_user, user.staff_profile
        return user, None

    def validate_client_id(self, value):
        user = self.context['request'].user
        owner, _ = self._get_owner(user)
        if not Client.objects.filter(id=value, user=owner).exists():
            raise serializers.ValidationError("Client not found.")
        return value

    def validate_appointment_date(self, value):
        today = timezone.now().date()
        if value < today:
            raise serializers.ValidationError("Cannot book appointments in the past.")

        user = self.context['request'].user
        owner, _ = self._get_owner(user)

        # Check against new DailyWorkingHours if set
        day_entry = DailyWorkingHours.objects.filter(
            user=owner, weekday=value.weekday()
        ).first()
        if day_entry and day_entry.is_off:
            raise serializers.ValidationError("Selected date is an off day.")

        # Fallback: check old WorkingHours
        if not day_entry and hasattr(owner, 'working_hours'):
            if not owner.working_hours.is_working_day(value):
                raise serializers.ValidationError("Selected date is an off day.")

        return value

    def validate_appointment_time(self, value):
        if value.minute not in [0, 15, 30, 45]:
            raise serializers.ValidationError(
                "Appointment time must be in 15-minute intervals."
            )
        return value

    def validate(self, data):
        user = self.context['request'].user
        owner, _ = self._get_owner(user)
        appt_date = data['appointment_date']
        appt_time = data['appointment_time']

        # Validate time is within working hours for this day
        day_entry = DailyWorkingHours.objects.filter(
            user=owner, weekday=appt_date.weekday()
        ).first()

        if day_entry and not day_entry.is_off:
            if not (day_entry.start_time <= appt_time < day_entry.end_time):
                raise serializers.ValidationError({
                    'appointment_time':
                        f"Time must be between {day_entry.start_time} and {day_entry.end_time}."
                })
        elif not day_entry and hasattr(owner, 'working_hours'):
            wh = owner.working_hours
            if not (wh.start_time <= appt_time < wh.end_time):
                raise serializers.ValidationError({
                    'appointment_time':
                        f"Time must be between {wh.start_time} and {wh.end_time}."
                })
        elif not day_entry and not hasattr(owner, 'working_hours'):
            raise serializers.ValidationError(
                "Working hours must be configured before creating appointments."
            )

        # Validate service_type_ids belong to owner
        service_type_ids = data.get('service_type_ids', [])
        if service_type_ids:
            found = ServiceType.objects.filter(
                id__in=service_type_ids, user=owner
            ).count()
            if found != len(service_type_ids):
                raise serializers.ValidationError({
                    'service_type_ids': "One or more service IDs are invalid."
                })

        # Calculate duration of selected services
        services = ServiceType.objects.filter(id__in=service_type_ids, user=owner)
        services_duration = sum(s.service_time_minutes for s in services)

        processing_time = data.get('processing_time') or 0
        blocked_time = data.get('blocked_time') or 0
        extra_servicing = data.get('extra_servicing') or 0

        total_duration = services_duration + processing_time + blocked_time + extra_servicing
        intervals = (total_duration + 14) // 15
        current_time = datetime.combine(appt_date, appt_time)

        for i in range(intervals):
            slot_time = (current_time + timedelta(minutes=15 * i)).time()



            available, slot = TimeSlotBooking.is_slot_available(owner, appt_date, slot_time)
            if not available:
                raise serializers.ValidationError({
                    'appointment_time': f"The time slot at {slot_time.strftime('%H:%M')} is fully booked ({slot.current_bookings}/{slot.max_capacity})."
                })

        self.context['owner'] = owner
        self.context['total_duration'] = total_duration
        return data

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        owner, sub_user = self._get_owner(user)
        total_duration = self.context.get('total_duration')

        client = Client.objects.get(id=validated_data['client_id'])
        service_type_ids = validated_data.get('service_type_ids', [])

        # Pick first service as FK (appointment model supports single FK)
        service_type_obj = None
        if service_type_ids:
            service_type_obj = ServiceType.objects.filter(
                id=service_type_obj or service_type_ids[0], user=owner
            ).first()

        # Build a combined service name if multiple selected
        if service_type_ids and not validated_data.get('service_name'):
            names = list(
                ServiceType.objects.filter(
                    id__in=service_type_ids, user=owner
                ).values_list('name', flat=True)
            )
            service_name = ", ".join(names)
        else:
            service_name = validated_data.get('service_name', '')

        appointment = Appointment.objects.create(
            user=owner,
            sub_user=sub_user,
            client=client,
            appointment_date=validated_data['appointment_date'],
            appointment_time=validated_data['appointment_time'],
            appointment_type='manual',
            service_type=service_type_obj,
            service_name=service_name,
            reminder_hours=validated_data.get('reminder_hours'),
            notes=validated_data.get('notes', ''),
            processing_time=validated_data.get('processing_time'),
            blocked_time=validated_data.get('blocked_time'),
            extra_servicing=validated_data.get('extra_servicing'),
        )

        if total_duration is None:
            services = ServiceType.objects.filter(id__in=service_type_ids, user=owner)
            services_duration = sum(s.service_time_minutes for s in services)
            processing_time = validated_data.get('processing_time') or 0
            blocked_time = validated_data.get('blocked_time') or 0
            extra_servicing = validated_data.get('extra_servicing') or 0
            total_duration = services_duration + processing_time + blocked_time + extra_servicing

        intervals = (total_duration + 14) // 15
        current_time = datetime.combine(appointment.appointment_date, appointment.appointment_time)

        for i in range(intervals):
            slot_time = (current_time + timedelta(minutes=15 * i)).time()
            slot = TimeSlotBooking.get_or_create_slot(owner, appointment.appointment_date, slot_time)
            slot.increment_booking()

        # Update client's next appointment date
        client.next_appointment_date = appointment.appointment_date
        client.save(update_fields=['next_appointment_date', 'updated_at'])

        # Send email (same helper as original)
        from .serializers import send_appointment_email
        send_appointment_email(appointment)

        return appointment


class NewAppointmentDetailSerializer(serializers.ModelSerializer):
    """Read serializer for the new appointment (returned after create)."""
    client_name = serializers.SerializerMethodField()
    client_contact = serializers.SerializerMethodField()
    client_email = serializers.SerializerMethodField()
    client_image = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    is_past = serializers.ReadOnlyField()
    is_today = serializers.ReadOnlyField()
    service_display = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()

    total_time = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'client_name', 'client_contact', 'client_email', 'client_image',
            'appointment_date', 'appointment_time',
            'service_display', 'services',
            'status', 'appointment_type',
            'reminder_hours', 'reminder_sent',
            'notes',
            'processing_time', 'blocked_time', 'extra_servicing', 'total_time',
            'created_by', 'is_past', 'is_today',
            'created_at', 'updated_at',
        ]

    def get_client_name(self, obj):
        return obj.get_client_name()

    def get_client_contact(self, obj):
        return obj.get_client_contact()

    def get_client_email(self, obj):
        return obj.get_client_email()

    def get_client_image(self, obj):
        if obj.client and obj.client.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.client.profile_image.url)
        return None

    def get_created_by(self, obj):
        if obj.appointment_type == 'self_booked':
            return {'type': 'client', 'name': obj.client_name}
        elif obj.sub_user:
            return {'type': 'staff', 'name': obj.sub_user.name, 'id': str(obj.sub_user.id)}
        return {'type': 'owner', 'name': obj.user.name or obj.user.email, 'id': str(obj.user.id)}

    def get_service_display(self, obj):
        return obj.service_name or obj.get_service_display()

    def get_total_time(self, obj):
        services_data = self.get_services(obj)
        service_time_minutes = sum(s.get('service_time_minutes') or 0 for s in services_data)
        
        processing_time = obj.processing_time or 0
        blocked_time = obj.blocked_time or 0
        extra_servicing = obj.extra_servicing or 0
        
        return service_time_minutes + processing_time + blocked_time + extra_servicing

    def get_services(self, obj):
        """Return list of services from service_type FK + service_name."""
        result = []
        owner = obj.user
        
        if obj.service_name:
            names = [n.strip() for n in obj.service_name.split(',') if n.strip()]
            services = ServiceType.objects.filter(user=owner, name__in=names)
            service_map = {s.name: s for s in services}
            
            for name in names:
                if name in service_map:
                    s = service_map[name]
                    result.append({
                        'id': s.id,
                        'name': s.name,
                        'service_time_minutes': s.service_time_minutes,
                        'price_type': s.price_type,
                        'service_fee': str(s.service_fee) if s.service_fee else None,
                    })
                else:
                    result.append({'id': None, 'name': name})
        
        if not result and obj.service_type:
            s = obj.service_type
            result.append({
                'id': s.id,
                'name': s.name,
                'service_time_minutes': s.service_time_minutes,
                'price_type': s.price_type,
                'service_fee': str(s.service_fee) if s.service_fee else None,
            })
            
        return result


# ===========================================================================
# 4. NEW CLIENT SELF-BOOKING
# ===========================================================================

class NewSelfBookingSerializer(serializers.Serializer):
    """
    POST /appointment/book/<token>/new/
    A random client books via the salon owner's unique link.
    """
    client_name = serializers.CharField(max_length=255)
    client_contact = serializers.CharField(max_length=20, required=False, allow_blank=True)
    client_email = serializers.EmailField(required=False, allow_blank=True)
    appointment_date = serializers.DateField()
    appointment_time = serializers.TimeField()
    service_type = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of ServiceType IDs"
    )
    service_type_id = serializers.IntegerField(
        required=False,
        help_text="ID from the salon's service list (fallback)"
    )

    def validate_appointment_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Cannot book in the past.")
        return value

    def validate_appointment_time(self, value):
        if value.minute not in [0, 15, 30, 45]:
            raise serializers.ValidationError("Please select a 15-minute interval.")
        return value

    def validate(self, data):
        token = self.context.get('token')
        try:
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=token, is_active=True
            )
        except AppointmentURL.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive booking URL.")

        owner = appointment_url.user
        appt_date = data['appointment_date']
        appt_time = data['appointment_time']
        
        service_ids = data.get('service_type', [])
        if isinstance(service_ids, int):
            service_ids = [service_ids]
        elif isinstance(service_ids, str):
            try:
                service_ids = [int(x.strip()) for x in service_ids.split(',') if x.strip()]
            except ValueError:
                pass

        if not service_ids and 'service_type_id' in data:
            service_ids = [data['service_type_id']]

        if not service_ids:
            raise serializers.ValidationError("Please select at least one service.")

        # Validate services belong to owner
        services = list(ServiceType.objects.filter(id__in=service_ids, user=owner))
        if len(services) != len(service_ids):
            raise serializers.ValidationError("One or more selected services are invalid.")

        # Check working hours (prefer new DailyWorkingHours)
        day_entry = DailyWorkingHours.objects.filter(
            user=owner, weekday=appt_date.weekday()
        ).first()

        total_duration = sum(s.service_time_minutes for s in services)
        intervals = (total_duration + 14) // 15
        current_time = datetime.combine(appt_date, appt_time)

        for i in range(intervals):
            slot_time = (current_time + timedelta(minutes=15 * i)).time()

            if day_entry:
                if day_entry.is_off:
                    raise serializers.ValidationError({
                        'appointment_date': "Selected date is not available."
                    })
                if not (day_entry.start_time <= slot_time < day_entry.end_time):
                    raise serializers.ValidationError({
                        'appointment_time': "Appointment duration exceeds working hours."
                    })
            elif hasattr(owner, 'working_hours'):
                wh = owner.working_hours
                if not wh.is_working_day(appt_date):
                    raise serializers.ValidationError({
                        'appointment_date': "Selected date is not available."
                    })
                if not (wh.start_time <= slot_time < wh.end_time):
                    raise serializers.ValidationError({
                        'appointment_time': "Appointment duration exceeds working hours."
                    })
            else:
                raise serializers.ValidationError("Booking is currently unavailable.")

            available, slot = TimeSlotBooking.is_slot_available(owner, appt_date, slot_time)
            if not available:
                raise serializers.ValidationError({
                    'appointment_time': f"The time slot at {slot_time.strftime('%H:%M')} is fully booked."
                })

        self.context['owner'] = owner
        self.context['services'] = services
        self.context['total_duration'] = total_duration
        return data

    @transaction.atomic
    def create(self, validated_data):
        owner = self.context['owner']
        services = self.context['services']
        total_duration = self.context['total_duration']

        primary_service = services[0] if services else None
        service_names = ", ".join([s.name for s in services])

        appointment = Appointment.objects.create(
            user=owner,
            sub_user=None,
            client=None,
            appointment_type='self_booked',
            service_type=primary_service,
            service_name=service_names,
            client_name=validated_data['client_name'],
            client_contact=validated_data.get('client_contact', ''),
            client_email=validated_data.get('client_email', ''),
            appointment_date=validated_data['appointment_date'],
            appointment_time=validated_data['appointment_time'],
        )

        intervals = (total_duration + 14) // 15
        current_time = datetime.combine(appointment.appointment_date, appointment.appointment_time)

        for i in range(intervals):
            slot_time = (current_time + timedelta(minutes=15 * i)).time()
            slot = TimeSlotBooking.get_or_create_slot(owner, appointment.appointment_date, slot_time)
            slot.increment_booking()

        from .serializers import send_appointment_email
        send_appointment_email(appointment)

        return appointment


class NewBookingPageSerializer(serializers.Serializer):
    """
    Read-only response for GET /appointment/book/<token>/new/
    Returns salon info + enriched services + available working hours.
    """
    salon_name = serializers.CharField()
    user_id = serializers.CharField()
    services = ServiceTypeDetailSerializer(many=True)
    working_hours = serializers.SerializerMethodField()

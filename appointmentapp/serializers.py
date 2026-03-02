# appointmentapp/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import secrets

from .models import (
    WorkingHours, ServiceType, AppointmentURL, 
    Appointment, TimeSlotBooking
)
from clientapp.models import Client
from authapp.models import User

from django.core.mail import send_mail
from django.conf import settings
# def send_appointment_email(appointment):
#     """Send appointment confirmation email"""
#     subject = f"Appointment Confirmation - {appointment.appointment_date}"
#     message = f"""
#     Dear {appointment.get_client_name()},
    
#     Your appointment has been confirmed:
    
#     Date: {appointment.appointment_date}
#     Time: {appointment.appointment_time}
#     Service: {appointment.service_type.name if appointment.service_type else 'N/A'}
    
#     Location: [Your Salon Address]
    
#     Looking forward to seeing you!
#     """
    
#     email = appointment.get_client_email()
#     if email:
#         send_mail(
#             subject,
#             message,
#             'noreply@yoursalon.com',
#             [email],
#             fail_silently=True
#         )
from django.core.mail import send_mail
from django.template.loader import render_to_string

def send_appointment_email(appointment):
    """Send confirmation to BOTH client and salon owner"""
    
    # Email to CLIENT
    client_subject = f"Appointment Confirmation - {appointment.appointment_date}"
    client_message = f"""
Dear {appointment.get_client_name()},

Your appointment has been confirmed!

📅 Date: {appointment.appointment_date}
🕐 Time: {appointment.appointment_time}
💇 Service: {appointment.get_service_display()}
📍 Salon: {appointment.user.name or appointment.user.email}

Thank you for booking with us!

---
My Colour Cost
"""
    
    client_email = appointment.get_client_email()
    if client_email:
        send_mail(
            client_subject,
            client_message,
            settings.EMAIL_HOST_USER,  # Change this'noreply@mycolourcost.com'
            [client_email],
            fail_silently=True
        )
    
    # Email to SALON OWNER
    owner_subject = f"New Appointment Booking - {appointment.appointment_date}"
    owner_message = f"""
New appointment booked!

👤 Client: {appointment.get_client_name()}
📞 Contact: {appointment.get_client_contact()}
📧 Email: {appointment.get_client_email()}
📅 Date: {appointment.appointment_date}
🕐 Time: {appointment.appointment_time}
💇 Service: {appointment.get_service_display()}
📝 Type: {appointment.get_appointment_type_display()}

---
My Colour Cost Dashboard
"""
    
    owner_email = appointment.user.email
    send_mail(
        owner_subject,
        owner_message,
        settings.EMAIL_HOST_USER,  # Change this'noreply@mycolourcost.com'
        [owner_email],
        fail_silently=True
    )
class WorkingHoursSerializer(serializers.ModelSerializer):
    """
    Serializer for setting working hours (one-time setup).
    """
    
    class Meta:
        model = WorkingHours
        fields = [
            'id', 'start_time', 'end_time', 'off_days', 
            'is_locked', 'created_at'
        ]
        read_only_fields = ['id', 'is_locked', 'created_at']
        extra_kwargs = {
            'off_days': {'write_only': True}  # Don't serialize from DB
        }
    off_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        write_only=True,  # Only for input
        help_text="List of off days (0=Monday, 6=Sunday)"
    )

    def to_representation(self, instance):
        """Convert off_days string back to list"""
        data = super().to_representation(instance)
        #data['off_days'] = instance.get_off_days_list()❌
        '''
        Exception Type: ValueError
        Exception Value:
        invalid literal for int() with base 10: ','
        '''
        #The error occurs because WorkingHoursSerializer.to_representation() is trying to convert the off_days string (e.g., "0,6") back to a list, but it's failing.

        if instance.off_days:
            data['off_days'] = [int(day) for day in instance.off_days.split(',') if day]
        else:
            data['off_days'] = []
        return data
    
    '''
    #**Remove this validation** - it's already validated by `IntegerField(min_value=0, max_value=6)`.
    
    def validate_off_days(self, value):
        """Validate off days format"""
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        days = [day.strip() for day in value.split(',')]
        
        for day in days:
            if day not in valid_days:
                raise serializers.ValidationError(
                    f"Invalid day: {day}. Must be one of {', '.join(valid_days)}"
                )
        return value
    '''

        
    def validate(self, data):
        """Validate working hours logic"""
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time'
                })
        
        # Check if user already has working hours set
        user = self.context['request'].user
        if WorkingHours.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "Working hours already set and cannot be changed"
            )
        return data
        
    @transaction.atomic
    def create(self, validated_data):
        """Create working hours and lock them"""
        off_days = validated_data.pop('off_days', [])
        
        # Convert off_days list to comma-separated string
        off_days_str = ','.join(map(str, off_days)) if off_days else ''
        
        working_hours = WorkingHours.objects.create(
            user=self.context['request'].user,
            off_days=off_days_str,
            is_locked=True,  # Lock immediately
            **validated_data
        )
        return working_hours
      #do I need them on the create?✅

    '''
      user = self.context['request'].user
        validated_data['user'] = user
        validated_data['is_locked'] = True  # Lock immediately after creation
        
        # Set team size based on role
        if user.role == 'owner':
            # For owners, team_size should come from input
            pass
        elif user.role == 'self_employed':
            validated_data['team_size'] = 1  # Self-employed always has team size 1
        
        return super().create(validated_data)
      '''


class ServiceTypeSerializer(serializers.ModelSerializer):
    """Serializer for service types offered by salon"""
    
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']
        
    def validate_name(self, value):
        """Validate service name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Service name is required")
        return value.strip()

class AppointmentURLCreateSerializer(serializers.Serializer):
    """
    Serializer for creating appointment URL (one-time setup).
    Owner provides list of services they offer.
    """
    services = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        help_text="List of services offered (e.g., ['Haircut', 'Coloring', 'Styling'])"
    )
    
    def validate(self, data):
        """Validate that user doesn't already have an appointment URL"""
        user = self.context['request'].user
        
        # Only owners can create appointment URLs
        if user.role != 'owner':
            raise serializers.ValidationError(
                "Only salon owners can create appointment URLs"
            )
        # Check if URL already exists
        if AppointmentURL.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "Appointment URL already exists for this user"
            )
        # Check if working hours are set
        if not hasattr(user, 'working_hours'):
            raise serializers.ValidationError(
                "Please set working hours before creating appointment URL"
            )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create appointment URL and services"""
        user = self.context['request'].user
        services = validated_data['services']
        
        # Generate unique token
        token = secrets.token_urlsafe(16)
        
        # Create appointment URL
        appointment_url = AppointmentURL.objects.create(
            user=user,
            token=token
        )
        # Create service types
        service_objects = []
        for service_name in services:
            service = ServiceType.objects.create(
                user=user,
                name=service_name.strip()
            )
            service_objects.append(service)
        
        # Return data for response
        return {
            'appointment_url': appointment_url,
            'services': service_objects
        }


class AppointmentURLSerializer(serializers.ModelSerializer):
    """Serializer for retrieving appointment URL"""
    services = ServiceTypeSerializer(source='user.service_types', many=True, read_only=True)
    booking_url = serializers.ReadOnlyField()
    
    class Meta:
        model = AppointmentURL
        fields = ['id', 'token', 'booking_url', 'services', 'is_active', 'created_at']
        read_only_fields = ['id', 'token', 'booking_url', 'created_at']


class TimeSlotAvailabilitySerializer(serializers.Serializer):
    """
    Serializer for checking time slot availability.
    Returns available slots for a given date.
    """
    date = serializers.DateField()
    
    def validate_date(self, value):
        """Validate date is not in the past"""
        today = timezone.now().date()
        if value < today:
            raise serializers.ValidationError("Cannot check availability for past dates")
        return value


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating manual appointments (by owner/staff).
    """
    client_id = serializers.IntegerField(write_only=True)
    service_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Service name (free text)"
    )
    reminder_hours = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1
    )
    
    class Meta:
        model = Appointment
        fields = [
            'client_id', 'appointment_date', 'appointment_time',
             'service_name','reminder_hours', 'notes'#'service_type',
        ]
    
    def validate_client_id(self, value):
        """Validate client exists and belongs to user"""
        user = self.context['request'].user
        
        # Get owner (could be user or user's owner if staff)
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # Check if client exists
        try:
            client = Client.objects.get(id=value, user=owner)
        except Client.DoesNotExist:
            raise serializers.ValidationError("Client not found")
        
        return value
    
    def validate_appointment_date(self, value):
        """Validate appointment date"""
        today = timezone.now().date()
        
        # Cannot book for past dates
        if value < today:
            raise serializers.ValidationError("Cannot book appointments in the past")
        
        # Check if date is a working day
        user = self.context['request'].user
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        if hasattr(owner, 'working_hours'):
            if not owner.working_hours.is_working_day(value):
                raise serializers.ValidationError("Selected date is an off day")
        
        return value
    
    def validate_appointment_time(self, value):
        """Validate appointment time is in 15-minute intervals"""
        if value.minute not in [0, 15, 30, 45]:
            raise serializers.ValidationError(
                "Appointment time must be in 15-minute intervals (e.g., 09:00, 09:15, 09:30)"
            )
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        user = self.context['request'].user
        appointment_date = data['appointment_date']
        appointment_time = data['appointment_time']
        
        # Get owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
        else:
            owner = user
        
        # Check working hours exist
        if not hasattr(owner, 'working_hours'):
            raise serializers.ValidationError(
                "Working hours must be set before creating appointments"
            )
        
        working_hours = owner.working_hours
        
        # Validate time is within working hours
        if not (working_hours.start_time <= appointment_time < working_hours.end_time):
            raise serializers.ValidationError({
                'appointment_time': f"Time must be between {working_hours.start_time} and {working_hours.end_time}"
            })
        
        # Check slot availability
        available, slot = TimeSlotBooking.is_slot_available(
            owner, appointment_date, appointment_time
        )
        
        if not available:
            raise serializers.ValidationError({
                'appointment_time': f"This time slot is fully booked ({slot.current_bookings}/{slot.max_capacity})"
            })
        
        # Store slot in context for use in create()
        self.context['time_slot'] = slot
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create appointment and update slot booking"""
        user = self.context['request'].user
        client_id = validated_data.pop('client_id')
        
        # Get client
        client = Client.objects.get(id=client_id)
        
        # Determine owner and sub_user
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            sub_user = user.staff_profile
        else:
            owner = user
            sub_user = None
        
        # Create appointment
        appointment = Appointment.objects.create(
            user=owner,
            sub_user=sub_user,
            client=client,
            appointment_type='manual',
            service_type=None,  # No FK for manual
            **validated_data
        )
        
        # Update slot booking count
        time_slot = self.context['time_slot']
        time_slot.increment_booking()
        
        # TODO: Send email notification
        # self.send_appointment_email(appointment)
        
        send_appointment_email(appointment)
        
        return appointment


class AppointmentSelfBookingSerializer(serializers.ModelSerializer):
    """
    Serializer for client self-booking via URL.
    Client provides their info + appointment details.
    """
    token = serializers.CharField(write_only=True, help_text="Appointment URL token")
    
    #ervice_type_id = serializers.IntegerField(write_only=True, source='service_type')
    # ✅ REMOVE source='service_type' - let it use the field name as-is
    service_type_id = serializers.IntegerField(write_only=True)
    '''
    Error: 
    if I pass string name" haircut " to service_type: 
    'Incorrect type. Expected pk value, received str'

    if I pass just Id I got "Invalid type choices"

    Reason: 
    The issue was that service_type is a ForeignKey in the model, so it expects an ID, but my validation logic checks for a name string.

    '''

    class Meta:
        model = Appointment
        fields = [
            'token', 'client_name', 'client_contact', 'client_email',
            'appointment_date', 'appointment_time', 'service_type_id'
        ]

    def validate_service_type_id(self, value):
        """Validate service type ID"""
        # Will be fully validated in validate() after we have the owner
        return value
    
    def validate_token(self, value):
        """Validate appointment URL token"""
        try:
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=value,
                is_active=True
            )
        except AppointmentURL.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive booking URL")
        
        # Store in context for later use
        self.context['appointment_url'] = appointment_url
        return value
    
    def validate_appointment_date(self, value):
        """Validate date is not in the past"""
        today = timezone.now().date()
        if value < today:
            raise serializers.ValidationError("Cannot book appointments in the past")
        return value
    
    def validate_appointment_date(self, value):
        """Validate date is not in the past"""
        today = timezone.now().date()
        if value < today:
            raise serializers.ValidationError("Cannot book appointments in the past")

        return value
    
    def validate_appointment_time(self, value):
        """Validate time is in 15-minute intervals"""
        if value.minute not in [0, 15, 30, 45]:
            raise serializers.ValidationError(
                "Please select a time in 15-minute intervals"
            )
        return value
    
    # def validate(self, data):
    #     """Cross-field validation"""
    #     appointment_url = self.context.get('appointment_url')
    #     if not appointment_url:
    #         raise serializers.ValidationError("Invalid booking URL")
        
    #     owner = appointment_url.user
    #     appointment_date = data['appointment_date']
    #     appointment_time = data['appointment_time']
    #     # service_type = data['service_type']
    #     #service_type_id = data['service_type']  # Note: it's already mapped to 'service_type' via source
        
    #     service_type_id = data.pop('service_type')  # Remove from data
    #     # Validate service type
    #     '''
    #     if not ServiceType.objects.filter(user=owner, name=service_type).exists():
    #         raise serializers.ValidationError({
    #             'service_type': "Invalid service type selected"
    #         })

    #     #Previously it was name based input for sevice type, but it's a foreignkey on the model, thats why getting error
    #     '''

    #     try:
    #         service_type = ServiceType.objects.get(id=service_type_id, user=owner)
    #         data['service_type'] = service_type  # Replace ID with object
    #     except ServiceType.DoesNotExist:
    #         raise serializers.ValidationError({
    #             'service_type_id': "Invalid service type selected"
    #         })
        
    #     # Check working hours
    #     if not hasattr(owner, 'working_hours'):
    #         raise serializers.ValidationError("Booking is currently unavailable")
        
    #     working_hours = owner.working_hours
        
    #     # Check if working day
    #     if not working_hours.is_working_day(appointment_date):
    #         raise serializers.ValidationError({
    #             'appointment_date': "Selected date is not available"
    #         })
        
    #     # Check if time is within working hours
    #     if not (working_hours.start_time <= appointment_time < working_hours.end_time):
    #         raise serializers.ValidationError({
    #             'appointment_time': f"Please select a time between {working_hours.start_time} and {working_hours.end_time}"
    #         })
        
    #     # Check slot availability
    #     available, slot = TimeSlotBooking.is_slot_available(
    #         owner, appointment_date, appointment_time
    #     )
        
    #     if not available:
    #         raise serializers.ValidationError({
    #             'appointment_time': "This time slot is fully booked. Please select another time."
    #         })
        
    #     # Store for create()
    #     self.context['owner'] = owner
    #     self.context['time_slot'] = slot

    #     self.context['service_type'] = service_type
        
    #     return data

    def validate(self, data):
        """Cross-field validation"""
        # ✅ Add logging
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Validating data: {data}")
        
        appointment_url = self.context.get('appointment_url')
        if not appointment_url:
            raise serializers.ValidationError("Invalid booking URL")
        
        owner = appointment_url.user
        appointment_date = data['appointment_date']
        appointment_time = data['appointment_time']
        
        service_type_id = data.pop('service_type_id')
        
        logger.info(f"Owner: {owner.email}, Date: {appointment_date}, Time: {appointment_time}, Service ID: {service_type_id}")
        
        # Validate service type
        try:
            service_type = ServiceType.objects.get(id=service_type_id, user=owner)
            data['service_type'] = service_type
            logger.info(f"Service type found: {service_type.name}")
        except ServiceType.DoesNotExist:
            logger.error(f"Service type {service_type_id} not found for owner {owner.email}")
            raise serializers.ValidationError({
                'service_type_id': "Invalid service type selected"
            })
        
        # Check working hours
        if not hasattr(owner, 'working_hours'):
            logger.error(f"Owner {owner.email} has no working hours")
            raise serializers.ValidationError("Booking is currently unavailable")
        
        working_hours = owner.working_hours
        logger.info(f"Working hours: {working_hours.start_time} - {working_hours.end_time}")
        
        # Check if working day
        if not working_hours.is_working_day(appointment_date):
            logger.warning(f"Date {appointment_date} is not a working day")
            raise serializers.ValidationError({
                'appointment_date': "Selected date is not available"
            })
        
        # Check if time is within working hours
        if not (working_hours.start_time <= appointment_time < working_hours.end_time):
            logger.warning(f"Time {appointment_time} outside working hours")
            raise serializers.ValidationError({
                'appointment_time': f"Please select a time between {working_hours.start_time} and {working_hours.end_time}"
            })
        
        # Check slot availability
        available, slot = TimeSlotBooking.is_slot_available(
            owner, appointment_date, appointment_time
        )
        
        logger.info(f"Slot availability: {available}, Current bookings: {slot.current_bookings}/{slot.max_capacity}")
        
        if not available:
            raise serializers.ValidationError({
                'appointment_time': "This time slot is fully booked. Please select another time."
            })
        
        # Store for create()
        self.context['owner'] = owner
        self.context['time_slot'] = slot
        self.context['service_type'] = service_type
        
        return data
    @transaction.atomic
    def create(self, validated_data):
        """Create self-booked appointment"""
                # ✅ Remove token from validated_data
        validated_data.pop('token', None)
        # ✅ Remove service_type if it was added in validate()
        validated_data.pop('service_type', None)

        owner = self.context['owner']
        time_slot = self.context['time_slot']
        service_type = self.context['service_type']

        # ✅ Log what's in validated_data
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Creating appointment with data: {validated_data}")

        try:
            # Create appointment
            appointment = Appointment.objects.create(
                user=owner,
                sub_user=None,  # No staff for self-booking
                client=None,    # No existing client
                appointment_type='self_booked',
                service_type=service_type,  # FK for self-booking
                service_name='',  # Empty for self-booking
                **validated_data
            )
        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}")
            raise
        # Update slot booking count
        time_slot.increment_booking()
        
        # TODO: Send confirmation email
        # self.send_confirmation_email(appointment)
        send_appointment_email(appointment)
        
        return appointment


class AppointmentListSerializer(serializers.ModelSerializer):
    """Serializer for listing appointments"""
    client_name = serializers.SerializerMethodField()
    client_contact = serializers.SerializerMethodField()
    client_image = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    is_past = serializers.ReadOnlyField()
    is_today = serializers.ReadOnlyField()

    service_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'client_name', 'client_contact', 'client_image',
            'appointment_date', 'appointment_time', #'service_type',
            'service_display','status', 'appointment_type', 'created_by',
            'is_past', 'is_today', 'created_at'
        ]
    
    def get_client_name(self, obj):
        return obj.get_client_name()
    
    def get_client_contact(self, obj):
        return obj.get_client_contact()
    
    def get_client_image(self, obj):
        """Get client profile image if exists"""
        if obj.client and obj.client.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.client.profile_image.url)
        return None
    
    def get_created_by(self, obj):
        """Return who created the appointment"""
        if obj.appointment_type == 'self_booked':
            return {'type': 'client', 'name': obj.client_name}
        elif obj.sub_user:
            return {'type': 'staff', 'name': obj.sub_user.name,'id': obj.sub_user.id}
        else:
            return {'type': 'owner', 'name': obj.user.name or obj.user.email,'id': obj.user.id}
    def get_service_display(self, obj):
        """Return service name from either source"""
        return obj.get_service_display()

class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single appointment"""
    client_name = serializers.SerializerMethodField()
    client_contact = serializers.SerializerMethodField()
    client_email = serializers.SerializerMethodField()
    client_image = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    is_past = serializers.ReadOnlyField()
    is_today = serializers.ReadOnlyField()
    
    service_display = serializers.SerializerMethodField()
    class Meta:
        model = Appointment
        fields = [
            'id', 'client_name', 'client_contact', 'client_email', 'client_image',
            'appointment_date', 'appointment_time', #'service_type',
            'service_display','status', 'appointment_type', 'reminder_hours', 'reminder_sent',
            'notes', 'created_by', 'is_past', 'is_today',
            'created_at', 'updated_at'
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
        else:
            return {'type': 'owner', 'name': obj.user.name or obj.user.email, 'id': str(obj.user.id)}
    def get_service_display(self, obj):
        return obj.get_service_display()

class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating appointment status"""
    
    class Meta:
        model = Appointment
        fields = ['status', 'notes']
    
    def validate_status(self, value):
        """Prevent changing status of past appointments"""
        if self.instance and self.instance.is_past and value != 'completed':
            raise serializers.ValidationError(
                "Cannot change status of past appointments except to 'completed'"
            )
        return value


class AvailableTimeSlotsSerializer(serializers.Serializer):
    """
    Response serializer for available time slots.
    """
    date = serializers.DateField()
    time_slot = serializers.TimeField()
    available_capacity = serializers.IntegerField()
    max_capacity = serializers.IntegerField()
    is_available = serializers.BooleanField()


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_clients = serializers.IntegerField()
    total_mixes = serializers.IntegerField()
    total_pending_appointments = serializers.IntegerField()
    total_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
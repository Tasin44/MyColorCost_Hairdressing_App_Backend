from django.shortcuts import render

# Create your views here.
# appointmentapp/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    WorkingHours, ServiceType, AppointmentURL,
    Appointment, TimeSlotBooking
)
from .serializers import (
    WorkingHoursSerializer, ServiceTypeSerializer,
    AppointmentURLCreateSerializer, AppointmentURLSerializer,
    TimeSlotAvailabilitySerializer, AppointmentCreateSerializer,
    AppointmentSelfBookingSerializer, AppointmentListSerializer,
    AppointmentDetailSerializer, AppointmentUpdateSerializer,
    AvailableTimeSlotsSerializer,DashboardStatsSerializer
)
from clientapp.models import Client
from mixapp.models import Mix
from django.shortcuts import render
import logging
logger = logging.getLogger(__name__)

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


class WorkingHoursSetupView(StandardResponseMixin, APIView):
    """
    Set working hours for user (ONE TIME ONLY).
    Once set, cannot be changed.
     Only for owner and self_employed roles.
    POST /appointment/working-hours/setup/
    Body: {
        "start_time": "09:00",
        "end_time": "20:00",
        "off_days": [0, 6]  // 0=Monday, 6=Sunday
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic #added by me 
    def post(self, request):
        """Create working hours (one-time setup)"""
        
        user = request.user
        
        # Check if user has permission
        if user.role not in ['owner', 'self_employed']:
            return self.error_response(
                "Only salon owners and self-employed users can configure working hours",
                status_code=403
            )
            
        # Check if already exists
        if WorkingHours.objects.filter(user=request.user).exists():
            return self.error_response(
                "Working hours already set and cannot be changed",
                status_code=400
            )
        
        serializer = WorkingHoursSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            working_hours = serializer.save()
            
            return self.success_response(
                data=WorkingHoursSerializer(working_hours).data,
                #what will happen if I just send data=serializer.data,❓
                message="Working hours set successfully",
                status_code=201
            )
        
        return self.error_response(
            "Failed to set working hours",
            status_code=400,
            data=serializer.errors
        )
    
    def get(self, request):
        """Get current working hours"""
        try:
            working_hours = request.user.working_hours
            serializer = WorkingHoursSerializer(working_hours)
            
            return self.success_response(
                data=serializer.data,
                message="Working hours retrieved successfully"
            )
        except WorkingHours.DoesNotExist:
            return self.error_response(
                "Working hours not set yet",
                status_code=404
            )


class AppointmentURLGenerateView(StandardResponseMixin, APIView):
    """
    Generate unique appointment booking URL (ONE TIME ONLY).
    Owner provides list of services offered.
    
    POST /appointment/generate-url/
    Body: {
        "services": ["Haircut", "Hair Coloring", "Hair Styling", "Treatment"]
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Generate appointment URL with services"""
        # Check if already exists
        
        user = request.user
        
        if AppointmentURL.objects.filter(user=user).exists():
            return self.error_response(
                "Appointment URL already exists",
                status_code=400
            )
            
            
        #----------added by me ✅

        # Check if user has working hours configured
        try:
            working_hours = user.working_hours
        except WorkingHours.DoesNotExist:
            return self.error_response(
                "Please configure working hours before generating booking link",
                status_code=400
            )#-----------------------------------
            
            
        serializer = AppointmentURLCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            
            response_data = {
                'appointment_url': AppointmentURLSerializer(result['appointment_url']).data,
                'services': ServiceTypeSerializer(result['services'], many=True).data
            }
            
            return self.success_response(
                data=response_data,
                message="Appointment URL generated successfully",
                status_code=201
            )
        
        return self.error_response(
            "Failed to generate appointment URL",
            status_code=400,
            data=serializer.errors
        )
    
    def get(self, request):
        """Get existing appointment URL and services"""
        try:
            appointment_url = request.user.appointment_url
            serializer = AppointmentURLSerializer(appointment_url)
            
            return self.success_response(
                data=serializer.data,
                message="Appointment URL retrieved successfully"
            )
        except AppointmentURL.DoesNotExist:
            return self.error_response(
                "Appointment URL not generated yet",
                status_code=404
            )


class AvailableTimeSlotsView(StandardResponseMixin, APIView):
    """
    Get available time slots for a specific date.
    Used by both manual booking and client self-booking.
    
    GET /appointment/available-slots/?date=2024-12-25
    Optional: &user_id=xxx (for client self-booking via URL)
    """
    permission_classes = [AllowAny]  # Allow unauthenticated for client booking
    
    def get(self, request):
        """Get available slots for a date"""
        date_str = request.query_params.get('date')
        user_id = request.query_params.get('user_id')  # For client self-booking
        
        if not date_str:
            return self.error_response(
                "Date parameter is required",
                status_code=400
            )
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()#this is the requested date 
        except ValueError:
            return self.error_response(
                "Invalid date format. Use YYYY-MM-DD",
                status_code=400
            )
        
        # Validate date is not in past
        if date < timezone.now().date():
            return self.error_response(
                "Cannot check availability for past dates",
                status_code=400
            )
        
        # Determine which user's slots to check
        if user_id:
            # Client self-booking - get owner by user_id
            try:
                from authapp.models import User
                user = User.objects.get(id=user_id, role='owner')
            except User.DoesNotExist:
                return self.error_response(
                    "Invalid user",
                    status_code=404
                )
        else:
            # Manual booking - use authenticated user
            if not request.user.is_authenticated:
                return self.error_response(
                    "Authentication required",
                    status_code=401
                )
            user = request.user
            
            # If staff, use owner
            if user.role == 'staff' and hasattr(user, 'staff_profile'):
                user = user.staff_profile.main_user
        
        # Check working hours exist
        if not hasattr(user, 'working_hours'):
            return self.error_response(
                "Working hours not configured",
                status_code=404
            )
        
        working_hours = user.working_hours
        
        # Check if date is a working day
        if not working_hours.is_working_day(date):
            return self.success_response(
                data={
                    'date': date,
                    'is_working_day': False,
                    'available_slots': []
                },
                message="Selected date is an off day"
            )
        
        # Generate all possible time slots for the day
        all_slots = working_hours.generate_time_slots()
        
        # Get existing bookings for this date
        existing_bookings = TimeSlotBooking.objects.filter(
            user=user,
            date=date
        ).select_related()
        
        # Create lookup dict for quick access
        booking_lookup = {
            booking.time_slot: booking
            for booking in existing_bookings
        }
        
        # Determine max capacity
        if user.role == 'owner':
            max_capacity = user.staff_limit if user.staff_limit > 0 else 1
        else:
            max_capacity = 1
        
        # Build available slots list
        available_slots = []
        for time_slot in all_slots:
            booking = booking_lookup.get(time_slot)
            
            if booking:
                current_bookings = booking.current_bookings
                is_available = current_bookings < max_capacity
            else:
                current_bookings = 0
                is_available = True
            
            available_slots.append({
                'time_slot': time_slot,
                'available_capacity': max_capacity - current_bookings,
                'max_capacity': max_capacity,
                'is_available': is_available
            })
        
        return self.success_response(
            data={
                'date': date,
                'is_working_day': True,
                'working_hours': {
                    'start_time': working_hours.start_time,
                    'end_time': working_hours.end_time
                },
                'available_slots': available_slots
            },
            message="Available slots retrieved successfully"
        )


class AppointmentCreateView(StandardResponseMixin, APIView):
    """
    Create manual appointment (by owner/staff).
    
    POST /appointment/create/
    Body: {
        "client_id": 123,
        "appointment_date": "2024-12-25",
        "appointment_time": "10:00",
        "service_type": "Haircut",
        "reminder_hours": 2,
        "notes": "Client prefers stylist Jane"
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Create new appointment"""
        user = request.user
        
        # Validate permissions
        if user.role not in ['owner', 'staff', 'self_employed']:
            return self.error_response(
                "You don't have permission to create appointments",
                status_code=403
            )
        
        # For staff, get the main user (owner)
        if user.role == 'staff':
            try:
                sub_user = user.staff_profile
                main_user = sub_user.main_user
            except:
                return self.error_response(
                    "Staff profile not found",
                    status_code=400
                )
        else:
            main_user = user
            sub_user = None
            
            
        serializer = AppointmentCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            appointment = serializer.save()
            
            detail_serializer = AppointmentDetailSerializer(
                appointment,
                context={'request': request}
            )
            
            return self.success_response(
                data=detail_serializer.data,
                message="Appointment created successfully",
                status_code=201
            )
        
        return self.error_response(
            "Failed to create appointment",
            status_code=400,
            data=serializer.errors
        )

       #----------------------------------------------- #----------added by me ✅
        #I want to add them during creation , is it possible
        #DON'T ADD IT - you'd be duplicating logic and breaking DRY principle.
        # Current flow is correct:
        # View → Serializer validation → Serializer.create() → Done 
        '''
        # Get validated data
        client_id = serializer.validated_data['client_id']
        appointment_date = serializer.validated_data['appointment_date']
        appointment_time = serializer.validated_data['appointment_time']
        service_type_id = serializer.validated_data.get('service_type_id')
        reminder_hours = serializer.validated_data.get('reminder_hours')
        notes = serializer.validated_data.get('notes', '')
        
        # Get client
        try:
            client = Client.objects.get(id=client_id, user=main_user)
        except Client.DoesNotExist:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        
        # Get or create time slot
        working_hours = main_user.working_hours
        time_slot, created = TimeSlot.objects.get_or_create(
            user=main_user,
            date=appointment_date,
            time=appointment_time,
            defaults={
                'total_capacity': working_hours.team_size,
                'booked_count': 0,
                'is_fully_booked': False
            }
        )
        
        # Check if slot can be booked
        if not time_slot.can_book():
            return self.error_response(
                "This time slot is fully booked",
                status_code=400
            )
        
        # Get service type
        service_type = None
        if service_type_id:
            try:
                service_type = ServiceType.objects.get(id=service_type_id, user=main_user)
            except ServiceType.DoesNotExist:
                pass
        
        # Create appointment
        appointment = Appointment.objects.create(
            user=main_user,
            sub_user=sub_user,
            client=client,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            service_type=service_type,
            time_slot=time_slot,
            booking_type='manual',
            status='scheduled',
            reminder_hours=reminder_hours,
            notes=notes
        )
        
        # Increment slot booking count
        time_slot.increment_booking()
        
        # Update client's next appointment date
        client.next_appointment_date = appointment_date
        client.save(update_fields=['next_appointment_date', 'updated_at'])
        
        # TODO: Send email notification to client
        # send_appointment_email(appointment)
        
        serializer = AppointmentDetailSerializer(appointment, context={'request': request})
        
        return self.success_response(
            data=serializer.data,
            message="Appointment created successfully",
            status_code=201
        )
        '''

      #---------------------------------------------------------------------------------/


# class AppointmentSelfBookingView(StandardResponseMixin, APIView):
#     """
#     Client self-booking endpoint (no authentication required).
#     Client accesses via unique URL token.
    
#     POST /appointment/book/{token}/
#     Body: {
#         "client_name": "John Doe",
#         "client_contact": "+1234567890",
#         "client_email": "john@example.com",
#         "appointment_date": "2024-12-25",
#         "appointment_time": "10:00",
#         "service_type": "Haircut"
#     }
#     """
#     permission_classes = [AllowAny]
    
#     @transaction.atomic
#     def post(self, request, token):
#         """Create self-booked appointment"""
#         # ✅ Log incoming request
#         logger.info(f"Self-booking attempt with token: {token}")
#         logger.info(f"Request data: {request.data}")
        
#         # Add token to request data
#         data = request.data.copy()
#         data['token'] = token
        
#         serializer = AppointmentSelfBookingSerializer(
#             data=data,
#             context={'request': request}
#         )
        
#         # ✅ Check validation errors in detail
#         if not serializer.is_valid():
#             logger.error(f"Validation errors: {serializer.errors}")
#             return self.error_response(
#                 "Failed to book appointment",
#                 status_code=400,
#                 data=serializer.errors  # ✅ This will show exact error
#             )
        
#         try:
#             appointment = serializer.save()
            
#             detail_serializer = AppointmentDetailSerializer(
#                 appointment,
#                 context={'request': request}
#             )
            
#             logger.info(f"Appointment created successfully: {appointment.id}")
            
#             return self.success_response(
#                 data=detail_serializer.data,
#                 message="Appointment booked successfully! Confirmation email sent.",
#                 status_code=201
#             )
#         except Exception as e:
#             logger.exception(f"Error creating appointment: {str(e)}")
#             return self.error_response(
#                 f"Error: {str(e)}",
#                 status_code=500
#             )
class AppointmentSelfBookingView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]
    
    # def get(self, request, token):
    #     """Get booking page info"""
    #     try:
    #         appointment_url = AppointmentURL.objects.select_related('user').get(
    #             token=token,
    #             is_active=True
    #         )
    #     except AppointmentURL.DoesNotExist:
    #         return self.error_response(
    #             "Invalid or inactive booking URL",
    #             status_code=404
    #         )
        
    #     owner = appointment_url.user
        
    #     # ✅ CHECK working hours FIRST
    #     if not hasattr(owner, 'working_hours'):
    #         return self.error_response(
    #             "Booking unavailable - working hours not set",
    #             status_code=400
    #         )
        
    #     wh = owner.working_hours
    #     working_hours_data = {
    #         'start_time': wh.start_time.strftime('%H:%M'),
    #         'end_time': wh.end_time.strftime('%H:%M'),
    #         'off_days': wh.get_off_days_list()
    #     }
        
    #     # ✅ FIX: Return services as list of dicts with id and name
    #     services = ServiceType.objects.filter(user=owner).values('id', 'name')
        
    #     logger.info(f"Services for {owner.email}: {list(services)}")
        
    #     return self.success_response(
    #         data={
    #             'salon_name': owner.name or owner.email,
    #             'user_id': owner.id,
    #             'services': list(services),  # ✅ This returns [{'id': 1, 'name': 'Haircut'}, ...]
    #             'working_hours': working_hours_data
    #         },
    #         message="Booking information retrieved successfully"
    #     )
    #I want to add it s logic, is it necessary?
    #Same as above - DON'T ADD IT. The serializer handles everything. 
    #Your commented code (lines 668-738) duplicates what AppointmentSelfBookingSerializer.create() already does.
    '''
           # Get validated data
        client_name = serializer.validated_data['client_name']
        client_contact = serializer.validated_data['client_contact']
        client_email = serializer.validated_data['client_email']
        appointment_date = serializer.validated_data['appointment_date']
        appointment_time = serializer.validated_data['appointment_time']
        service_type_id = serializer.validated_data['service_type_id']
        
        # Get service type
        try:
            service_type = ServiceType.objects.get(id=service_type_id, user=user)
        except ServiceType.DoesNotExist:
            return self.error_response(
                "Invalid service type",
                status_code=400
            )
        
        # Get or create time slot
        working_hours = user.working_hours
        time_slot, created = TimeSlot.objects.get_or_create(
            user=user,
            date=appointment_date,
            time=appointment_time,
            defaults={
                'total_capacity': working_hours.team_size,
                'booked_count': 0,
                'is_fully_booked': False
            }
        )
        
        # Check if slot can be booked
        if not time_slot.can_book():
            return self.error_response(
                "This time slot is fully booked",
                status_code=400
            )
        
        # Create appointment
        appointment = Appointment.objects.create(
            user=user,
            client_name=client_name,
            client_contact=client_contact,
            client_email=client_email,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            service_type=service_type,
            time_slot=time_slot,
            booking_type='client_self',
            status='scheduled'
        )
        
        # Increment slot booking count
        time_slot.increment_booking()
        
        # TODO: Send confirmation email to client
        # send_booking_confirmation_email(appointment)
        
        return self.success_response(
            data={
                'appointment_id': appointment.id,
                'appointment_date': appointment.appointment_date,
                'appointment_time': appointment.appointment_time,
                'service': service_type.service_name
            },
            message="Appointment booked successfully. You will receive a confirmation email.",
            status_code=201
        )
    
    
    '''
   
    '''
    def get(self, request, token):
        try:
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=token,
                is_active=True
            )
        except AppointmentURL.DoesNotExist:
            return self.error_response(
                "Invalid or inactive booking URL",
                status_code=404
            )
        
        owner = appointment_url.user
        
        # Get services
        services = ServiceType.objects.filter(user=owner).values_list('name', flat=True)
        
        # Get working hours
        working_hours_data = None
        if not hasattr(owner, 'working_hours'):
            return self.error_response(
                "Booking is currently unavailable, Owner didn't set working hours yet",
                status_code=404
        )
        if hasattr(owner, 'working_hours'):
            wh = owner.working_hours
            working_hours_data = {
                'start_time': wh.start_time.strftime('%H:%M'),
                'end_time': wh.end_time.strftime('%H:%M'),
                'off_days': wh.get_off_days_list()
            }
        
        return self.success_response(
            data={
                'salon_name': owner.name or owner.email,
                'services': list(services),
                'working_hours': working_hours_data,
                'user_id': str(owner.id)  # For checking available slots
            },
            message="Booking information retrieved successfully"
        )
    
    '''

    @transaction.atomic
    def post(self, request, token):
        """Create self-booked appointment"""
        data = request.data.copy()
        data['token'] = token
        
        serializer = AppointmentSelfBookingSerializer(
            data=data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return self.error_response(
                "Failed to book appointment",
                status_code=400,
                data=serializer.errors
            )
        
        try:
            appointment = serializer.save()
        except Exception as e:
            logger.exception(f"Error saving appointment: {str(e)}")
            return self.error_response(
                f"Server error: {str(e)}",
                status_code=500
            )
        detail_serializer = AppointmentDetailSerializer(
            appointment,
            context={'request': request}
        )
        return self.success_response(
            data=detail_serializer.data,
            message="Appointment booked successfully!",
            status_code=201
        )
    def get(self, request, token):
        """Get booking page info"""
        try:
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=token,
                is_active=True
            )
        except AppointmentURL.DoesNotExist:
            return self.error_response(
                "Invalid or inactive booking URL",
                status_code=404
            )
        
        owner = appointment_url.user
        
        if not hasattr(owner, 'working_hours'):
            return self.error_response(
                "Booking unavailable - working hours not set",
                status_code=400
            )
        
        wh = owner.working_hours
        
        # ✅ MUST return id and name, not flat list
        services = list(ServiceType.objects.filter(user=owner).values('id', 'name'))

        return self.success_response(
            data={
                'salon_name': owner.name or owner.email,
                'user_id': owner.id,
                'services': services,
                'working_hours': {
                    'start_time': wh.start_time.strftime('%H:%M'),
                    'end_time': wh.end_time.strftime('%H:%M'),
                    'off_days': wh.get_off_days_list()
                }
            },
            message="Booking information retrieved successfully"
        )
    # def get(self, request, token):
    #     """Get booking page info"""
    #     try:
    #         appointment_url = AppointmentURL.objects.select_related('user').get(
    #             token=token,
    #             is_active=True
    #         )
    #     except AppointmentURL.DoesNotExist:
    #         return self.error_response(
    #             "Invalid or inactive booking URL",
    #             status_code=404
    #         )
        
    #     owner = appointment_url.user
        
    #     # ✅ CHECK working hours FIRST
    #     if not hasattr(owner, 'working_hours'):
    #         return self.error_response(
    #             "Booking unavailable - working hours not set",
    #             status_code=400
    #         )
        
    #     # ✅ NOW safe to access
    #     wh = owner.working_hours
    #     working_hours_data = {
    #         'start_time': wh.start_time.strftime('%H:%M'),
    #         'end_time': wh.end_time.strftime('%H:%M'),
    #         'off_days': wh.get_off_days_list()
    #     }
        
    #     # Get services
    #     services = ServiceType.objects.filter(user=owner).values_list('name', flat=True)
    #     logger.info(f"Services for {owner.email}: {list(services)}")

    #     return self.success_response(
    #         # data={
    #         #     'salon_name': owner.name or owner.email,
    #         #     'services': list(services),
    #         #     'working_hours': working_hours_data,
    #         #     'user_id': str(owner.id)
    #         # },
    #         data={
    #             'salon_name': owner.name or owner.email,
    #             'user_id': owner.id,
    #             'services': list(services),  # ✅ Convert QuerySet to list
    #             'working_hours': {
    #                 'start_time': owner.working_hours.start_time.strftime('%H:%M'),
    #                 'end_time': owner.working_hours.end_time.strftime('%H:%M'),
    #                 'off_days': owner.working_hours.get_off_days_list()
    #             }
    #         },
    #         message="Booking information retrieved successfully"
    #     )

class AppointmentListView(StandardResponseMixin, APIView):
    """
    List appointments with filtering.
    
    GET /appointment/list/
    Query params:
    - date: Filter by specific date (YYYY-MM-DD)
    - status: Filter by status (scheduled, completed, cancelled)
    - today: Get today's appointments (true/false)
    - upcoming: Get upcoming appointments (true/false)
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self, request):
        """Get appointments based on user role"""
        user = request.user
        
        # Base queryset
        queryset = Appointment.objects.select_related(
            'user', 'sub_user', 'client'
        )
        
        # Filter by role
        if user.role == 'owner':
            # Owner sees all appointments
            queryset = queryset.filter(user=user)
        elif user.role == 'staff' and hasattr(user, 'staff_profile'):
            # Staff sees their own appointments
            staff_profile = user.staff_profile
            queryset = queryset.filter(
                user=staff_profile.main_user,
                sub_user=staff_profile
            )
        else:
            # Self-employed sees their own
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def get(self, request):
        """Get list of appointments"""
        queryset = self.get_queryset(request)
        
        # Apply filters
        date_str = request.query_params.get('date')
        status_filter = request.query_params.get('status')
        today = request.query_params.get('today')
        upcoming = request.query_params.get('upcoming')
        
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(appointment_date=date)
            except ValueError:
                return self.error_response(
                    "Invalid date format. Use YYYY-MM-DD",
                    status_code=400
                )
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if today == 'true':
            today_date = timezone.now().date()
            queryset = queryset.filter(appointment_date=today_date)
        
        if upcoming == 'true':
            today_date = timezone.now().date()
            queryset = queryset.filter(
                appointment_date__gte=today_date,
                status='scheduled'
            )
        
        # Order by date and time
        queryset = queryset.order_by('appointment_date', 'appointment_time')
        
        serializer = AppointmentListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        
        return self.success_response(
            data={
                'appointments': serializer.data,
                'total_count': queryset.count()
            },
            message="Appointments retrieved successfully"
        )


class TodayAppointmentsView(StandardResponseMixin, APIView):
    """
    Get today's appointments for home page display.
    
    GET /appointment/today/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get today's appointments"""
        user = request.user
        
        '''
        today = timezone.now().date()
        
        # Get today's appointments
        if user.role == 'owner':
            appointments = Appointment.objects.filter(
                user=user,
                appointment_date=today
            ).select_related('client', 'sub_user').order_by('appointment_time')
        elif user.role == 'staff' and hasattr(user, 'staff_profile'):
            staff_profile = user.staff_profile
            appointments = Appointment.objects.filter(
                user=staff_profile.main_user,
                sub_user=staff_profile,
                appointment_date=today
            ).select_related('client').order_by('appointment_time')
        else:
            appointments = Appointment.objects.filter(
                user=user,
                appointment_date=today
            ).select_related('client').order_by('appointment_time')
        
        '''
        # For staff, get main user
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            main_user = user.staff_profile.main_user
        else:
            main_user = user
        
        today = timezone.now().date()
        
        appointments = Appointment.objects.select_related(
            'user', 'sub_user', 'client', 'service_type'
        ).filter(
            user=main_user,
            appointment_date=today
        ).order_by('appointment_time')
        
        # ✅ Add status breakdown
        stats = appointments.aggregate(
            total=Count('id'),
            scheduled=Count('id', filter=Q(status='scheduled')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled'))
        )
            
        serializer = AppointmentListSerializer(
            appointments,
            many=True,
            context={'request': request}
        )
        
        return self.success_response(
            data={
                'date': today,
                'appointments': serializer.data,
                # 'total_count': appointments.count()
                'total_appointments': stats['total'],
                'scheduled': stats['scheduled'],
                'completed': stats['completed'],
                'cancelled': stats['cancelled'],
            },
            message="Today's appointments retrieved successfully"
        )
        
#I want to take help from the below method if possible improve logically
'''
class TodayAppointmentsView(StandardResponseMixin, APIView):
    """
    Get today's appointments for home page dashboard.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get today's appointments"""
        user = request.user
        
        # For staff, get main user
        if user.role == 'staff':
            try:
                sub_user = user.staff_profile
                main_user = sub_user.main_user
            except:
                return self.error_response(
                    "Staff profile not found",
                    status_code=400
                )
        else:
            main_user = user
        
        today = timezone.now().date()
        
        # Get today's appointments
        appointments = Appointment.objects.select_related(
            'user', 'sub_user', 'client', 'service_type'
        ).filter(
            user=main_user,
            appointment_date=today
        ).order_by('appointment_time')
        
        # Count by status
        stats = appointments.aggregate(
            total=Count('id'),
            scheduled=Count('id', filter=Q(status='scheduled')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled'))
        )
        
        serializer = AppointmentListSerializer(
            appointments,
            many=True,
            context={'request': request}
        )
        
        return self.success_response(
            data={
                'total_appointments': stats['total'],
                'scheduled': stats['scheduled'],
                'completed': stats['completed'],
                'cancelled': stats['cancelled'],
                'appointments': serializer.data
            },
            message="Today's appointments retrieved successfully"
        )


'''

class AppointmentDetailView(StandardResponseMixin, APIView):
    """
    Get, update, or delete specific appointment.
    
    GET /appointment/{appointment_id}/
    PATCH /appointment/{appointment_id}/
    DELETE /appointment/{appointment_id}/
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, request, appointment_id):
        """Get appointment if user has access"""
        user = request.user
        
        try:
            if user.role == 'staff' and hasattr(user, 'staff_profile'):
                # Staff can only access their appointments
                appointment = Appointment.objects.select_related(
                    'user', 'sub_user', 'client'
                ).get(
                    id=appointment_id,
                    user=user.staff_profile.main_user,
                    sub_user=user.staff_profile
                )
            else:
                # Owner/self-employed can access their appointments
                appointment = Appointment.objects.select_related(
                    'user', 'sub_user', 'client'
                ).get(
                    id=appointment_id,
                    user=user
                )
            
            return appointment
        except Appointment.DoesNotExist:
            return None
    
    def get(self, request, appointment_id):
        """Get appointment details"""
        appointment = self.get_object(request, appointment_id)
        
        if not appointment:
            return self.error_response(
                "Appointment not found",
                status_code=404
            )
        
        serializer = AppointmentDetailSerializer(
            appointment,
            context={'request': request}
        )
        
        return self.success_response(
            data=serializer.data,
            message="Appointment retrieved successfully"
        )
    
    @transaction.atomic
    def patch(self, request, appointment_id):
        """Update appointment (status, notes)"""
        appointment = self.get_object(request, appointment_id)
        
        if not appointment:
            return self.error_response(
                "Appointment not found",
                status_code=404
            )
        
        serializer = AppointmentUpdateSerializer(
            appointment,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            appointment = serializer.save()
            
            detail_serializer = AppointmentDetailSerializer(
                appointment,
                context={'request': request}
            )
            
            return self.success_response(
                data=detail_serializer.data,
                message="Appointment updated successfully"
            )
        
        return self.error_response(
            "Failed to update appointment",
            status_code=400,
            data=serializer.errors
        )
    
    @transaction.atomic
    def delete(self, request, appointment_id):
        """Cancel/delete appointment"""
        appointment = self.get_object(request, appointment_id)
        
        if not appointment:
            return self.error_response(
                "Appointment not found",
                status_code=404
            )
        
        # Update slot booking count
        try:
            slot = TimeSlotBooking.objects.get(
                user=appointment.user,
                date=appointment.appointment_date,
                time_slot=appointment.appointment_time
            )
            slot.decrement_booking()
        except TimeSlotBooking.DoesNotExist:
            pass
        
        # Delete appointment
        client_name = appointment.get_client_name()
        appointment.delete()
        
        return self.success_response(
            message=f"Appointment for {client_name} cancelled successfully"
        )


class AppointmentStatsView(StandardResponseMixin, APIView):
    """
    Get appointment statistics for dashboard.
    
    GET /appointment/stats/
    """
    permission_classes = [IsAuthenticated]
    
    '''
    def get(self, request):
        """Get appointment statistics"""
        user = request.user
        today = timezone.now().date()
        
        # Get base queryset
        if user.role == 'owner':
            appointments = Appointment.objects.filter(user=user)
        elif user.role == 'staff' and hasattr(user, 'staff_profile'):
            staff_profile = user.staff_profile
            appointments = Appointment.objects.filter(
                user=staff_profile.main_user,
                sub_user=staff_profile
            )
        else:
            appointments = Appointment.objects.filter(user=user)
        
        # Calculate stats
        stats = {
            'total_appointments': appointments.count(),
            'today_appointments': appointments.filter(appointment_date=today).count(),
            'upcoming_appointments': appointments.filter(
                appointment_date__gte=today,
                status='scheduled'
            ).count(),
            'completed_appointments': appointments.filter(status='completed').count(),
            'cancelled_appointments': appointments.filter(status='cancelled').count(),
        }
        
        return self.success_response(
            data=stats,
            message="Appointment statistics retrieved successfully"
        )
    '''
    def get(self, request):
          user = request.user
          
          # For staff, get main user
          if user.role == 'staff' and hasattr(user, 'staff_profile'):
              main_user = user.staff_profile.main_user
          else:
              main_user = user
          
          all_appointments = Appointment.objects.filter(user=main_user)
          
          today = timezone.now().date()
          week_start = today - timedelta(days=today.weekday())
          month_start = today.replace(day=1)
          
          stats = all_appointments.aggregate(
              total=Count('id'),
              scheduled=Count('id', filter=Q(status='scheduled')),
              completed=Count('id', filter=Q(status='completed')),
              cancelled=Count('id', filter=Q(status='cancelled')),
              no_show=Count('id', filter=Q(status='no_show')),
              today=Count('id', filter=Q(appointment_date=today)),
              this_week=Count('id', filter=Q(appointment_date__gte=week_start)),
              this_month=Count('id', filter=Q(appointment_date__gte=month_start))
          )
          
          return self.success_response(
              data=stats,
              message="Appointment statistics retrieved successfully"
      )
#I want to take logical help from the below method if possible to make it more better
'''
class AppointmentStatsView(StandardResponseMixin, APIView):
    """
    Get appointment statistics for dashboard.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get appointment statistics"""
        user = request.user
        
        # For staff, get main user
        if user.role == 'staff':
            try:
                sub_user = user.staff_profile
                main_user = sub_user.main_user
            except:
                return self.error_response(
                    "Staff profile not found",
                    status_code=400
                )
        else:
            main_user = user
        
        # Get all appointments
        all_appointments = Appointment.objects.filter(user=main_user)
        
        # Date ranges
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Aggregate statistics
        stats = all_appointments.aggregate(
            total=Count('id'),
            scheduled=Count('id', filter=Q(status='scheduled')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            no_show=Count('id', filter=Q(status='no_show')),
            today=Count('id', filter=Q(appointment_date=today)),
            this_week=Count('id', filter=Q(appointment_date__gte=week_start)),
            this_month=Count('id', filter=Q(appointment_date__gte=month_start))
        )
        
        return self.success_response(
            data={
                'total_appointments': stats['total'],
                'scheduled': stats['scheduled'],
                'completed': stats['completed'],
                'cancelled': stats['cancelled'],
                'no_show': stats['no_show'],
                'appointments_today': stats['today'],
                'appointments_this_week': stats['this_week'],
                'appointments_this_month': stats['this_month']
            },
            message="Appointment statistics retrieved successfully"
        )

'''
class CleanupOldSlotsView(StandardResponseMixin, APIView):
    """
    Cleanup old time slot bookings (admin/cron job).
    Deletes slots from past dates.
    
    POST /appointment/cleanup-slots/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Run cleanup of old slots"""
        # Only allow admins or scheduled tasks
        if not request.user.is_staff:
            return self.error_response(
                "Permission denied",
                status_code=403
            )
        
        deleted_count = TimeSlotBooking.cleanup_old_slots()
        
        return self.success_response(
            data={'deleted_count': deleted_count},
            message=f"Cleaned up {deleted_count} old time slot bookings"
        )




class DashboardStatsView(StandardResponseMixin, APIView):
    """Get dashboard statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get aggregated dashboard statistics"""
        user = request.user
        
        # Determine owner
        if user.role == 'staff' and hasattr(user, 'staff_profile'):
            owner = user.staff_profile.main_user
            staff_profile = user.staff_profile
        else:
            owner = user
            staff_profile = None
        
        # Total clients
        total_clients = Client.objects.filter(user=owner).count()
        
        # Total mixes (based on role)
        if staff_profile:
            # Staff sees only their mixes
            total_mixes = Mix.objects.filter(user=owner, sub_user=staff_profile).count()
            total_profit = Mix.objects.filter(
                user=owner, sub_user=staff_profile
            ).aggregate(Sum('profit'))['profit__sum'] or Decimal('0.00')
        else:
            # Owner sees all mixes
            total_mixes = Mix.objects.filter(user=owner).count()
            total_profit = Mix.objects.filter(user=owner).aggregate(
                Sum('profit')
            )['profit__sum'] or Decimal('0.00')
        
        # Total pending appointments
        total_pending_appointments = Appointment.objects.filter(
            user=owner,
            status='scheduled',
            appointment_date__gte=timezone.now().date()
        ).count()
        
        stats = {
            'total_clients': total_clients,
            'total_mixes': total_mixes,
            'total_pending_appointments': total_pending_appointments,
            'total_profit': total_profit
        }
        
        serializer = DashboardStatsSerializer(data=stats)
        serializer.is_valid()
        
        return self.success_response(
            data=serializer.data,
            message="Dashboard statistics retrieved successfully",
            status_code=200
        )

# class BookingPageView(APIView):
#     """Render HTML booking page"""
#     permission_classes = [AllowAny]
    
#     def get(self, request, token):
#         """Render booking page template"""
#         try:
#             appointment_url = AppointmentURL.objects.get(token=token, is_active=True)
#             return render(request, 'appointmentapp/booking_page.html', {'token': token})
#         except AppointmentURL.DoesNotExist:
#             return render(request, 'appointmentapp/invalid_link.html')
# ...existing code...

# class BookingPageView(APIView):
#     permission_classes = [AllowAny]
    
#     def get(self, request, token):
#         """Return booking page data as JSON for AJAX"""
#         try:
#             appointment_url = AppointmentURL.objects.select_related('user').get(
#                 token=token,
#                 is_active=True
#             )
#         except AppointmentURL.DoesNotExist:
#             return Response({
#                 'success': False,
#                 'message': 'Invalid booking link'
#             }, status=404)
        
#         # Get working hours
#         try:
#             working_hours = WorkingHours.objects.get(user=appointment_url.user)
#         except WorkingHours.DoesNotExist:
#             return Response({
#                 'success': False,
#                 'message': 'Working hours not configured'
#             }, status=400)
        
#         # Get services
#         services = ServiceType.objects.filter(user=appointment_url.user).values('id', 'name')
        
#         return Response({
#             'success': True,
#             'data': {
#                 'user_id': appointment_url.user.id,
#                 'salon_name': appointment_url.user.name or 'Our Salon',
#                 'services': list(services),
#                 'working_hours': {
#                     'start_time': working_hours.start_time.strftime('%H:%M'),
#                     'end_time': working_hours.end_time.strftime('%H:%M'),
#                     'off_days': working_hours.get_off_days_list()
#                 }
#             }
#         })

# ...existing code...

class BookingPageView(APIView):
    """
    Render HTML booking page for clients (no auth required).
    This just serves the HTML template. The JavaScript in the template
    will fetch booking data from AppointmentSelfBookingView.get()
    """
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        """Render booking page HTML template"""
        try:
            # Verify token exists and is active
            appointment_url = AppointmentURL.objects.select_related('user').get(
                token=token,
                is_active=True
            )
            
            # Just render the HTML template
            # JavaScript will handle data fetching via AJAX
            return render(
                request, 
                'appointmentapp/booking_page.html',
                {'token': token}
            )
            
        except AppointmentURL.DoesNotExist:
            # Optionally create an error page template
            return render(
                request,
                'appointmentapp/invalid_link.html',
                {'message': 'Invalid or expired booking link'},
                status=404
            )

# ...existing code...
# ...existing code...
from django.db import models

# Create your models here.
# appointmentapp/models.py

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from authapp.models import SubUser
from clientapp.models import Client
import uuid
from datetime import datetime, time, timedelta


class WorkingHours(models.Model):
    """
    Stores working schedule for each user (owner/self_employed/staff).
    Set ONCE and cannot be changed to maintain booking integrity.
    """
    
    WEEKDAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to user (owner/self_employed/staff)
    #❓why here  OneToOneField, why not ForeignKey?
    '''
    ans: 
    Reason: Each user should have only ONE working hours configuration. 
    OneToOneField enforces this 1:1 relationship. ForeignKey would allow multiple WorkingHours 
    per user (wrong).
    '''
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='working_hours',
        db_index=True
    )
    
    
    # Working hours (same for all working days)
    #why this type of help_text needed? ❓
    start_time = models.TimeField(
        help_text="Daily start time (e.g., 09:00 AM)"
    )
    end_time = models.TimeField(
        help_text="Daily end time (e.g., 08:00 PM)"
    )
    
    # Off days (stored as comma-separated integers: "0,6" = Monday,Sunday off)
    #It stores multiple off days as a comma-separated string
    off_days = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text="Comma-separated weekday numbers (0=Monday, 6=Sunday)"
    )
    
    # Lock to prevent changes after setup
    is_locked = models.BooleanField(
        default=True,
        help_text="Once set, working hours cannot be changed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'working_hours'
        verbose_name_plural = 'Working Hours'
    
    def __str__(self):
        return f"{self.user.email} - {self.start_time} to {self.end_time}"
    
    def get_off_days_list(self):
        """Convert off_days string to list of integers"""
        if not self.off_days:
            return []
        return [int(day) for day in self.off_days.split(',')]
    
    def is_working_day(self, date):
        """Check if given date is a working day"""
        weekday = date.weekday()  # 0=Monday, 6=Sunday
        return weekday not in self.get_off_days_list()
    
    def generate_time_slots(self):
        """
        Generate all possible 15-minute time slots for a day.
        Returns list of time objects.
        """
        slots = []
        current_time = datetime.combine(datetime.today(), self.start_time)
        end_datetime = datetime.combine(datetime.today(), self.end_time)
        
        while current_time < end_datetime:
            slots.append(current_time.time())
            current_time += timedelta(minutes=15)
        
        return slots


class ServiceType(models.Model):
    """
    Services offered by salon owner for client self-booking.
    Created once during appointment URL generation.
    """
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id = models.AutoField(primary_key=True)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='service_types',
        db_index=True
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Service name (e.g., Haircut, Coloring, etc.)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'service_types'
        unique_together = ('user', 'name')#it's service_name
        ordering = ['name']
    
    def __str__(self):
        return f"{self.user.email} - {self.name}"


class AppointmentURL(models.Model):
    """
    Unique appointment booking URL for each owner.
    Generated ONCE and reused for all client bookings.
    """
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id = models.AutoField(primary_key=True)
    
    # Only owners can have appointment URLs
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointment_url',
        limit_choices_to={'role': 'owner'},
        db_index=True
    )
    
    # Unique token for URL (e.g., /book/abc123xyz)
    token = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique URL token for booking page"
    )
    
    # Full URL will be: https://yourdomain.com/book/{token}
    
    is_active = models.BooleanField(
        default=True,
        help_text="URL can be deactivated to stop accepting bookings"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'appointment_urls'
        indexes = [
            models.Index(fields=['token']),
        ]
    def __str__(self):
        return f"{self.user.email} - /book/{self.token}"
    
    @property
    def booking_url(self):
        """Generate full booking URL"""
        # In production, replace with actual domain
        #return f"http://10.10.12.14:8000/book/{self.token}"
        #return f"http://10.10.12.14:8000/appointment/book/{self.token}/" 
        return f"{settings.BASE_URL}/appointment/book/{self.token}/"  # ✅ Changed


class Appointment(models.Model):
    """
    Main appointment model.
    Handles both manual creation and client self-booking.
    """
    
    APPOINTMENT_TYPE_CHOICES = (
        ('manual', 'Manual (Created by Owner/Staff)'),
        ('self_booked', 'Self-Booked (Client via URL)'),
    )
    
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    )
    
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id = models.AutoField(primary_key=True)#✅
    # ==================== RELATIONSHIPS ====================
    
    # Owner who owns this appointment slot
    #why using ForeignKey, why no OneToOneField❓
    '''
    ans: 
    Reason: One user can have MANY appointments (1:Many relationship).
    OneToOneField would limit each user to only 1 appointment (wrong).
    
    '''
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointments',
        db_index=True,
        help_text="Salon owner who owns this appointment"
    )
    
    # Staff who created/handles this appointment (optional)
    #why using ForeignKey, why no OneToOneField❓
    sub_user = models.ForeignKey(
        SubUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        db_index=True,
        help_text="Staff member handling this appointment"
    )
    
    # Client (for manual booking with existing clients)
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='appointments',
        db_index=True,
        help_text="Existing client (manual booking only)"
    )
    
    # ==================== CLIENT INFO (for self-booking) ====================
    # These fields are filled when client books via URL (no existing Client object)
    
    client_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Client name (for self-booking)"
    )
    client_contact = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Client contact number (for self-booking)"
    )
    client_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Client email (for self-booking)"
    )
    
    # ==================== APPOINTMENT DETAILS ====================
    
    appointment_date = models.DateField(
        db_index=True,
        help_text="Date of appointment"
    )
    
    appointment_time = models.TimeField(
        db_index=True,
        help_text="Time of appointment (15-min intervals)"
    )
    '''
    service_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Service requested by client"
    )
    '''
    service_type = models.ForeignKey(#✅

        ServiceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text="Type of service requested"
    )

    # Add new field for manual string input
    service_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Service name (for manual booking - free text)"
    )

    appointment_type = models.CharField(
        max_length=20,
        choices=APPOINTMENT_TYPE_CHOICES,
        default='manual',
        db_index=True,
        help_text="How this appointment was created"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        db_index=True
    )
    # ==================== REMINDER ====================
    
    reminder_hours = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Send reminder X hours before appointment"
    )
    
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Track if reminder email was sent"
    )
    
    # ==================== METADATA ====================
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about appointment"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'appointments'
        indexes = [
            # Most common queries: appointments by date and user
            models.Index(fields=['user', 'appointment_date', 'appointment_time']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['client', 'appointment_date']),
            models.Index(fields=['appointment_date', 'appointment_time', 'status']),
        ]
        ordering = ['-appointment_date', '-appointment_time']
    
    def __str__(self):
        client_display = self.client.name if self.client else self.client_name
        return f"{client_display} - {self.appointment_date} {self.appointment_time}"
    
    def get_client_name(self):
        """Get client name from either Client object or self-booked data"""
        if self.client:
            return self.client.name
        return self.client_name
    
    def get_client_contact(self):
        """Get client contact from either source"""
        if self.client:
            return self.client.contact_number
        return self.client_contact
    
    def get_client_email(self):
        """Get client email from either source"""
        if self.client:
            return self.client.email
        return self.client_email
    
    def get_service_display(self):
        """Get service display text from either source"""
        if self.service_type:
            return self.service_type.name
        return self.service_name or "N/A"
    
    @property
    def is_past(self):
        """Check if appointment is in the past"""
        from django.utils import timezone
        appointment_datetime = datetime.combine(
            self.appointment_date,
            self.appointment_time
        )
        # return appointment_datetime < timezone.now() #❌TypeError at /appointment/create/, can't compare offset-naive and offset-aware datetimes
        # Make it timezone-aware
        '''
        Why the error occurred:

        Python has two types of datetime objects:
        Naive datetime - No timezone info (e.g., "2:00 PM" - but where?)
        Aware datetime - Has timezone info (e.g., "2:00 PM UTC")

        # This creates a NAIVE datetime (no timezone)
        appointment_datetime = datetime.combine(
            self.appointment_date,
            self.appointment_time
        )  # Result: 2026-02-10 10:00:00 (no timezone)

        # This creates an AWARE datetime (has timezone)
        timezone.now()  # Result: 2026-02-04 15:30:00+00:00 (UTC timezone)

        # Python can't compare them!
        appointment_datetime < timezone.now()  # ❌ ERROR!
                

        It's like comparing "10 AM" with "10 AM New York Time" - Python doesn't know if they're the same moment.
        Why it's solved now:
        appointment_datetime = timezone.make_aware(appointment_datetime)

        This adds timezone information to your naive datetime, making both datetimes "aware":

        # Before: 2026-02-10 10:00:00 (naive)
        # After:  2026-02-10 10:00:00+06:00 (aware - uses Django's TIME_ZONE setting)

        # Now both are aware, so comparison works!
        aware_appointment < timezone.now()  # ✅ Works!

        In short: You can only compare apples to apples. make_aware() converted your "apple" (naive) into an "orange" (aware) so they match.
        '''
        appointment_datetime = timezone.make_aware(appointment_datetime)
        return appointment_datetime < timezone.now()
    
    @property
    def is_today(self):
        """Check if appointment is today"""
        return self.appointment_date == timezone.now().date()


class TimeSlotBooking(models.Model):
    """
    Tracks slot availability for each time slot on each day.
    Implements slot capacity logic based on team size.
    
    For owner with team_size=5: can book 5 appointments at same time
    For self_employed: can book 1 appointment at same time
    Staff bookings count toward owner's capacity.
    """
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id = models.AutoField(primary_key=True)#✅
    # Owner who owns thes slots
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_slot_bookings',
        db_index=True
    )
    
    date = models.DateField(db_index=True)
    time_slot = models.TimeField(db_index=True)
    
    # Track how many bookings exist for this slot
    #booking count 
    current_bookings = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current number of bookings for this slot"
    )
    
    # Maximum capacity based on user role
    max_capacity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Max bookings allowed (team_size for owner, 1 for self_employed)"
    )
    
    # Quick check if slot is full
    is_full = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True when current_bookings >= max_capacity"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'time_slot_bookings'
        unique_together = ('user', 'date', 'time_slot')
        indexes = [
            models.Index(fields=['user', 'date', 'is_full']),
            models.Index(fields=['date', 'time_slot']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.date} {self.time_slot} ({self.current_bookings}/{self.max_capacity})"
    
    def has_capacity(self):
        """Check if slot still has available capacity"""
        return self.current_bookings < self.max_capacity
        
    def can_book(self):#✅

        """Check if slot can accept more bookings"""
        return self.current_bookings < self.max_capacity and not self.is_full
        
    def increment_booking(self):
        """
        Increment booking count and update is_full status.
        Call this when a new appointment is created.
        """
        if not self.can_book():
            return False  # ✅ Return False if can't book
        
        self.current_bookings += 1
        if self.current_bookings >= self.max_capacity:
            self.is_full = True
        self.save(update_fields=['current_bookings', 'is_full', 'updated_at'])
        return True  # ✅ Return True on success
    
    def decrement_booking(self):
        """
        Decrement booking count when appointment is cancelled.
        """
        if self.current_bookings > 0:
            self.current_bookings -= 1
            self.is_full = False
            self.save(update_fields=['current_bookings', 'is_full', 'updated_at'])
            return True
        return False
    
    @classmethod
    def get_or_create_slot(cls, user, date, time_slot):
        """
        Get or create a TimeSlotBooking for given date/time.
        Automatically sets max_capacity based on user role.
        """
        # Determine max capacity based on user role
        if user.role == 'owner':
            max_capacity = user.staff_limit if user.staff_limit > 0 else 1
        elif user.role == 'self_employed':
            max_capacity = 1
        elif user.role == 'staff' and hasattr(user, 'staff_profile'):
            # Staff bookings use owner's capacity
            owner = user.staff_profile.main_user
            max_capacity = owner.staff_limit if owner.staff_limit > 0 else 1
        else:
            max_capacity = 1
        
        slot, created = cls.objects.get_or_create(
            user=user,
            date=date,
            time_slot=time_slot,
            defaults={'max_capacity': max_capacity}
        )
        return slot
    
    @classmethod
    def is_slot_available(cls, user, date, time_slot):
        """
        Check if a slot is available for booking.
        Returns (available, slot_obj)
        """
        slot = cls.get_or_create_slot(user, date, time_slot)
        return slot.has_capacity(), slot
    
    @classmethod
    def cleanup_old_slots(cls):
        """
        Delete slot bookings from past dates.
        Run this as a scheduled task (e.g., daily cron job).
        """
        yesterday = timezone.now().date() - timedelta(days=1)
        deleted_count = cls.objects.filter(date__lt=yesterday).delete()[0]
        return deleted_count
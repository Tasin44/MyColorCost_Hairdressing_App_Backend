# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
import uuid
from django.core.validators import MinValueValidator

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Add role field
    ROLE_CHOICES = (
        ('owner', 'Salon Owner'),#Salon Owner with Staff
        ('self_employed', 'Self-employed Hairdresser'),
        ('staff', 'Salon Staff'),
        ('retailer', 'Retailer'),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        null=True,
        blank=True,
        db_index=True
    )
    '''
    role → this is selected at the very first step in your UI.

    Owner → later chooses account_type

    Staff → role=staff + provide owner_email

    Retailer → role=retailer
    '''
    name = models.CharField(max_length=150, null=True, blank=True)
    image = models.ImageField(upload_to="profile_images/", null=True, blank=True)
    email = models.EmailField(unique=False)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    # For Google Signup
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    # Staff configuration (only for salon_owner_with_staff)
    staff_limit = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of staff members allowed. 0 means no staff."
    )
    notification_enabled = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Account type configuration
    # ACCOUNT_TYPE_CHOICES = (
    #     ('salon_owner_with_staff', 'Salon Owner with Staff'),
    #     ('self_employed', 'Self-employed Hairdresser'),
    # )
    # account_type = models.CharField(
    #     max_length=30, 
    #     choices=ACCOUNT_TYPE_CHOICES,
    #     null=True,  # Will be set after OTP verification
    #     blank=True,
    #     db_index=True
    # )
    # Resolve reverse accessor conflicts
    groups = models.ManyToManyField(
        'auth.Group', 
        related_name='authapp_user_set', 
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='authapp_user_set',
        blank=True
    )

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            # models.Index(fields=['account_type']),
        ]

    def __str__(self):
        #return f"{self.email} ({self.get_account_type_display()})"
        return f"{self.email} ({self.get_role_display()})"
    
    def can_add_staff(self):
        """Check if user can add more staff members"""
        # if self.account_type != 'salon_owner_with_staff':
        if self.role != 'owner':  # ✅ Changed
            return False
        
        current_staff_count = self.sub_users.filter(is_active=True).count()
        return current_staff_count < self.staff_limit
    
    def get_staff_count(self):
        """Get current active staff count"""
        return self.sub_users.filter(is_active=True).count()
    
class OTP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()#self.expires_at just means the expiry time stored in that OTP object in signup serializer
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'is_used']),
        ]
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
    
    def __str__(self):
        return f"{self.email} - {self.otp_code}"
    
    @classmethod
    def cleanup_expired(cls):
        """
        Utility method to clean up expired OTPs.
        Should be called periodically via cron job or celery task.
        """
        expired_time = timezone.now() - timezone.timedelta(hours=1)
        cls.objects.filter(created_at__lt=expired_time).delete()
        
# class ProfileImage(models.Model):
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     image = models.ImageField(upload_to="profile_images/", null=True, blank=True)


class SubUser(models.Model):
    """
    Staff members under a salon owner.
    Only exists when main user is 'salon_owner_with_staff'.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to main salon owner
    main_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sub_users',
        db_index=True
    )
    #SubUser FK to User
    user = models.OneToOneField(#null=True, blank=True because SubUser can exist before the actual user signs up.Once staff signs up, you link it to the actual User object.
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_profile'
    )
    #This allows owner to register staff emails first without passwords.
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),   # pre-registered but not signed up yet
        ('ACTIVE', 'Active'),     # staff has signed up & verified OTP
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    # Staff information
    name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(unique=True, db_index=True)
    
    # Status
    is_active = models.BooleanField(default=False, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sub_users'
        indexes = [
            models.Index(fields=['main_user', 'is_active']),
            models.Index(fields=['email']),
        ]
        ordering = ['name']
        # Ensure email is unique
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                name='unique_subuser_email'
            )
        ]
    
    def __str__(self):
        return f"{self.name} (Staff of {self.main_user.email})"
    








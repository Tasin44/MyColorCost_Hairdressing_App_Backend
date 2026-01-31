from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
from authapp.models import SubUser

class Client(models.Model):
    """
    Customer/Client model. 
    Linked to salon owner (user) and optionally to staff (sub_user).
    Optimized with proper indexes for fast queries.
    """
    id = models.AutoField(primary_key=True)

    # Relationships - salon owner who own this client 
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clients',
        db_index=True,
        help_text="Salon owner who owns this client"
    )
    
    # Relationships - salon subuser who own this client 
    sub_user = models.ForeignKey(
        SubUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        db_index=True,
        help_text="Staff member who created/manages this client (optional)"
    )
    
    # Client basic information
    name = models.CharField(max_length=255, db_index=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True, db_index=True)
    
    # Profile image
    profile_image = models.ImageField(
        upload_to='client_profiles/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Client profile photo"
    )

    # Service information
    service_type = models.CharField(#service name
        max_length=100, 
        null=True, 
        blank=True,
    )
    
    # Skin test tracking
    skin_test_date = models.DateField(null=True, blank=True)
    
    # Additional notes
    notes = models.TextField(null=True, blank=True)
    
    # Statistics - will be updated via signals or direct updates
    total_mixes = models.IntegerField(default=0, db_index=True)
    
    # Visit tracking -⏭️⏭️⏭️ will try to do this field using  property decorator from appointment model later 
    last_visit_date = models.DateTimeField(null=True, blank=True, db_index=True)
    next_appointment_date = models.DateField(null=True, blank=True, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clients'
        indexes = [
            # Composite index for owner lookups
            models.Index(fields=['user', 'name']),
            # Composite index for staff lookups
            models.Index(fields=['sub_user', 'name']),
            # Index for filtering by visit dates
            models.Index(fields=['user', 'last_visit_date']),
            models.Index(fields=['user', 'next_appointment_date']),
            # Search optimization
            models.Index(fields=['name', 'email']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.email}"
    
    def update_stats(self):
        """
        Update client statistics.
        Should be called after creating/deleting mixes.
        """
        from mixapp.models import Mix
        from django.db.models import Sum, Max
        
        # Get mix statistics efficiently
        mix_stats = self.mixes.aggregate(
            total_count=models.Count('id'),
            latest_date=Max('created_date')
        )
        
        self.total_mixes = mix_stats['total_count'] or 0
        self.last_visit_date = mix_stats['latest_date']
        self.save(update_fields=['total_mixes', 'last_visit_date', 'updated_at'])


class ClientImage(models.Model):
    """
    Before and After photos for clients.
    Uses efficient file storage and indexing.
    """
    IMAGE_TYPE_CHOICES = (
        ('before', 'Before'),
        ('after', 'After'),
    )
    
    id = models.AutoField(primary_key=True)
    
    # Relationship
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='images',
        db_index=True
    )
    
    # Image details
    image_type = models.CharField(
        max_length=10,
        choices=IMAGE_TYPE_CHOICES,
        db_index=True
    )
    
    # Store image with organized path: client_images/{client_id}/{image_type}/{filename}
    image = models.ImageField(
        upload_to='client_images/%Y/%m/%d/',
        help_text="Client before/after photo"
    )
    
    # Metadata
    upload_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'client_images'
        indexes = [
            # Composite index for client image lookups
            models.Index(fields=['client', 'image_type']),
            models.Index(fields=['client', 'upload_date']),
        ]
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.client.name} - {self.image_type} ({self.upload_date.date()})"
    

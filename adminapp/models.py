from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings

class AdminActivity(models.Model):
    """Track admin actions for audit purposes"""
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_activities'
    )
    action_type = models.CharField(max_length=100)
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_activities'
        ordering = ['-created_at']
from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
import uuid


class TermsAndConditions(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField(help_text="Full terms and conditions text")
    version = models.CharField(
        max_length=20,
        help_text="e.g. 1.0, 1.1, 2.0",
        default="1.0"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only one active terms should exist at a time"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='terms_updated',
        help_text="Superuser who last updated the terms"
    )
    type = models.CharField(
        max_length=20,
        choices=[
            ('app', 'App'),
            ('retailer', 'Retailer')
        ],
         default='app'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'terms_and_conditions'
        ordering = ['-updated_at']
        verbose_name = "Terms and Conditions"
        verbose_name_plural = "Terms and Conditions"

    def __str__(self):
        return f"Terms v{self.version} - updated {self.updated_at.strftime('%Y-%m-%d')}"

# ...existing code...

class PrivacyPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField(help_text="Full privacy policy text")
    version = models.CharField(
        max_length=20,
        help_text="e.g. 1.0, 1.1, 2.0",
        default="1.0"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only one active privacy policy should exist at a time"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='privacy_policy_updated',
        help_text="Superuser who last updated the privacy policy"
    )
    type = models.CharField(
        max_length=20,
        choices=[
            ('app', 'App'),
            ('retailer', 'Retailer')
        ],
        default='app'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'privacy_policy'
        ordering = ['-updated_at']
        verbose_name = "Privacy Policy"
        verbose_name_plural = "Privacy Policies"

    def __str__(self):
        return f"Privacy Policy v{self.version} - updated {self.updated_at.strftime('%Y-%m-%d')}"
    

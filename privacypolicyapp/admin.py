from django.contrib import admin
from .models import TermsAndConditions, PrivacyPolicy


@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(admin.ModelAdmin):
    list_display = ['version', 'is_active', 'updated_by', 'updated_at']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ['version', 'is_active', 'updated_by', 'updated_at']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']
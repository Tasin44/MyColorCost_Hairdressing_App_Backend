from rest_framework import serializers
from .models import TermsAndConditions


class TermsAndConditionsReadSerializer(serializers.ModelSerializer):
    """Used for GET — public read"""

    class Meta:
        model = TermsAndConditions
        fields = ['id', 'content', 'version', 'updated_at']


class TermsAndConditionsUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH — superuser only"""

    class Meta:
        model = TermsAndConditions
        fields = ['content', 'version']
        extra_kwargs = {
            'content': {'required': False},
            'version': {'required': False},
        }

    def validate_version(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Version cannot be blank.")
        return value.strip() if value else value

    def validate_content(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Content cannot be blank.")
        return value.strip() if value else value
# ...existing code...

from .models import TermsAndConditions, PrivacyPolicy


# ...existing code...


class PrivacyPolicyReadSerializer(serializers.ModelSerializer):
    """Used for GET — public read"""

    class Meta:
        model = PrivacyPolicy
        fields = ['id', 'content', 'version', 'updated_at']


class PrivacyPolicyUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH — superuser only"""

    class Meta:
        model = PrivacyPolicy
        fields = ['content', 'version']
        extra_kwargs = {
            'content': {'required': False},
            'version': {'required': False},
        }

    def validate_version(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Version cannot be blank.")
        return value.strip() if value else value

    def validate_content(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Content cannot be blank.")
        return value.strip() if value else value
    

from .models import TermsAndConditions, PrivacyPolicy


# ---------------- RETAILER TERMS ---------------- #

class RetailerTermsReadSerializer(serializers.ModelSerializer):
    """Retailer dashboard GET"""

    class Meta:
        model = TermsAndConditions
        fields = ['id', 'content', 'version', 'updated_at']


class RetailerTermsUpdateSerializer(serializers.ModelSerializer):
    """Admin PATCH"""

    class Meta:
        model = TermsAndConditions
        fields = ['content', 'version']
        extra_kwargs = {
            'content': {'required': False},
            'version': {'required': False},
        }


# ---------------- RETAILER PRIVACY POLICY ---------------- #

class RetailerPrivacyReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = PrivacyPolicy
        fields = ['id', 'content', 'version', 'updated_at']


class RetailerPrivacyUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = PrivacyPolicy
        fields = ['content', 'version']
        extra_kwargs = {
            'content': {'required': False},
            'version': {'required': False},
        }






















from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from .models import TermsAndConditions,PrivacyPolicy

from .serializers import (
    TermsAndConditionsReadSerializer, 
    TermsAndConditionsUpdateSerializer,
    PrivacyPolicyReadSerializer,
    PrivacyPolicyUpdateSerializer,

    RetailerTermsReadSerializer,
    RetailerTermsUpdateSerializer,
    RetailerPrivacyReadSerializer,
    RetailerPrivacyUpdateSerializer
)



class TermsAndConditionsView(APIView):
    """
    GET  /terms/   → Public. Returns the current active terms.
    PATCH /terms/  → Superuser only. Update terms content/version.
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        """Public endpoint — app fetches latest active terms"""
        terms = TermsAndConditions.objects.filter(is_active=True).order_by('-updated_at').first()

        if not terms:
            return Response(
                {
                    "success": False,
                    "statusCode": 404,
                    "message": "No terms and conditions found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TermsAndConditionsReadSerializer(terms)
        return Response(
            {
                "success": True,
                "statusCode": 200,
                "message": "Terms and conditions retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        """Superuser only — update terms and conditions"""

        # ✅ Only superuser can patch
        if not request.user.is_superuser:
            return Response(
                {
                    "success": False,
                    "statusCode": 403,
                    "message": "Permission denied. Only superusers can update terms and conditions."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Get the active terms or create one if none exists
        terms = TermsAndConditions.objects.filter(is_active=True).order_by('-updated_at').first()

        if not terms:
            # First time — create it
            terms = TermsAndConditions.objects.create(
                content=request.data.get('content', ''),
                version=request.data.get('version', '1.0'),
                is_active=True,
                updated_by=request.user
            )
            serializer = TermsAndConditionsReadSerializer(terms)
            return Response(
                {
                    "success": True,
                    "statusCode": 201,
                    "message": "Terms and conditions created successfully.",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        # Update existing
        serializer = TermsAndConditionsUpdateSerializer(
            terms,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            updated_terms = serializer.save(updated_by=request.user)
            read_serializer = TermsAndConditionsReadSerializer(updated_terms)
            return Response(
                {
                    "success": True,
                    "statusCode": 200,
                    "message": "Terms and conditions updated successfully.",
                    "data": read_serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "success": False,
                "statusCode": 400,
                "message": "Update failed.",
                "data": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
# ...existing code...


# ...existing code...


class PrivacyPolicyView(APIView):
    """
    GET  /privacy-policy/   → Public. Returns the current active privacy policy.
    PATCH /privacy-policy/  → Superuser only. Update privacy policy content/version.
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        """Public endpoint — app fetches latest active privacy policy"""
        policy = PrivacyPolicy.objects.filter(is_active=True).order_by('-updated_at').first()

        if not policy:
            return Response(
                {
                    "success": False,
                    "statusCode": 404,
                    "message": "No privacy policy found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PrivacyPolicyReadSerializer(policy)
        return Response(
            {
                "success": True,
                "statusCode": 200,
                "message": "Privacy policy retrieved successfully.",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        """Superuser only — update privacy policy"""

        if not request.user.is_superuser:
            return Response(
                {
                    "success": False,
                    "statusCode": 403,
                    "message": "Permission denied. Only superusers can update the privacy policy."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        policy = PrivacyPolicy.objects.filter(is_active=True).order_by('-updated_at').first()

        if not policy:
            # First time — create it
            policy = PrivacyPolicy.objects.create(
                content=request.data.get('content', ''),
                version=request.data.get('version', '1.0'),
                is_active=True,
                updated_by=request.user
            )
            serializer = PrivacyPolicyReadSerializer(policy)
            return Response(
                {
                    "success": True,
                    "statusCode": 201,
                    "message": "Privacy policy created successfully.",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        # Update existing
        serializer = PrivacyPolicyUpdateSerializer(
            policy,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            updated_policy = serializer.save(updated_by=request.user)
            read_serializer = PrivacyPolicyReadSerializer(updated_policy)
            return Response(
                {
                    "success": True,
                    "statusCode": 200,
                    "message": "Privacy policy updated successfully.",
                    "data": read_serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "success": False,
                "statusCode": 400,
                "message": "Update failed.",
                "data": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )





# ---------------- RETAILER TERMS API ---------------- #

class RetailerTermsView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):

        terms = TermsAndConditions.objects.filter(is_active=True).order_by('-updated_at').first()

        if not terms:
            return Response(
                {"message": "Retailer terms not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RetailerTermsReadSerializer(terms)

        return Response(
            {
                "success": True,
                "data": serializer.data
            }
        )

    def patch(self, request):

        if not request.user.is_superuser:
            return Response(
                {"message": "Only admin can update retailer terms"},
                status=status.HTTP_403_FORBIDDEN
            )

        terms = TermsAndConditions.objects.filter(is_active=True).first()

        serializer = RetailerTermsUpdateSerializer(
            terms,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save(updated_by=request.user)

            return Response({
                "success": True,
                "message": "Retailer terms updated successfully",
                "data": serializer.data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------- RETAILER PRIVACY POLICY API ---------------- #

class RetailerPrivacyPolicyView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):

        policy = PrivacyPolicy.objects.filter(is_active=True).order_by('-updated_at').first()

        if not policy:
            return Response(
                {"message": "Retailer privacy policy not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RetailerPrivacyReadSerializer(policy)

        return Response({
            "success": True,
            "data": serializer.data
        })

    def patch(self, request):

        if not request.user.is_superuser:
            return Response(
                {"message": "Only admin can update retailer privacy policy"},
                status=status.HTTP_403_FORBIDDEN
            )

        policy = PrivacyPolicy.objects.filter(is_active=True).first()

        serializer = RetailerPrivacyUpdateSerializer(
            policy,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save(updated_by=request.user)

            return Response({
                "success": True,
                "message": "Retailer privacy policy updated successfully",
                "data": serializer.data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    
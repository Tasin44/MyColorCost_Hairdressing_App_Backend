from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import random
import string

from .serializers import (
    SignupSerializer, AccountTypeSelectionSerializer, VerifyOTPSerializer, 
    ResendOTPSerializer, LoginSerializer, ForgotPasswordSerializer, 
    ResetPasswordSerializer, ProfileUpdateSerializer, ConfirmDeleteUserSerializer,
    MeSerializer, SubUserSerializer, SubUserCreateSerializer,SubUserInviteResponseSerializer
)
from .models import OTP, SubUser

User = get_user_model()


# ============================================
# SUB-USER (STAFF) MANAGEMENT VIEWS
# ============================================
# class StandardResponseMixin:
#     """Mixin for consistent API responses across all endpoints"""
    
#     def success_response(self, data=None, message="Success", status_code=200):
#         """Standard success response format"""
#         return Response({
#             "success": True,
#             "statusCode": status_code,
#             "message": message,
#             "data": data
#         }, status=status_code)
    
#     def error_response(self, message, status_code=400, data=None):
#         """Standard error response format"""
#         return Response({
#             "success": False,
#             "statusCode": status_code,
#             "message": message,
#             "data": data
#         }, status=status_code)
class StandardResponseMixin:
    def success_response(self, data=None, message="Success", status_code=200):
        response = {
            "success": True,
            "statusCode": status_code,
            "message": message,
        }

        if data is not None:
            response["data"] = data

        return Response(response, status=status_code)

    def error_response(self, message, status_code=400, data=None):
        response = {
            "success": False,
            "statusCode": status_code,
            "message": message,
        }

        if data is not None:
            response["data"] = data

        return Response(response, status=status_code)
    
class SignupView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        # serializer = SignupSerializer(data=request.data)
        serializer = SignupSerializer(
            data=request.data,
            context={"role": request.data.get("role")}
        )
        if serializer.is_valid():
            user = serializer.save()
            otp = serializer.context.get('otp')
            '''
            Original format in standard response: 
            def success_response(self, data, message="Success", status_code=200)

            but if I do:
            return self.success_response(
                {"email": user.email},   # data ✅
                {"name": user.name},    # ❌ THIS IS TREATED AS `message`
                message="User created. OTP sent to email.",  # ❌ message AGAIN
                status_code=201
            )
            ❌❌❌Got error: TypeError: StandardResponseMixin.success_response() got multiple values for argument 'message'

            '''
            data = {
                "email": user.email,
                "name": user.name,
                "otp": otp,  # DEV ONLY
                "contact_number":user.contact_number,
            }

            if user.role == "salon_owner":
                data["account_type"] = user.account_type

            return self.success_response(
                data=data,
                message="User created. OTP sent to email.",
                status_code=201
            )
        return self.error_response(
            "Signup failed",
            status_code=400,
            data=serializer.errors
        )


class VerifyOTPView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            otp = serializer.validated_data['otp']
            user = User.objects.get(email=otp.email)
            
            user.verified = True
            user.save(update_fields=['verified', 'updated_at'])
            
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            
            refresh = RefreshToken.for_user(user)
            return self.success_response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "name": user.name
                    }
                },
                message="Email verified successfully.",
                status_code=200
            )
        return self.error_response(
            "Verification failed",
            status_code=400,
            data=serializer.errors
        )


class ResendOTPView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            otp_code = ''.join(random.choices(string.digits, k=6))
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.filter(email=email, is_used=False).delete()
            OTP.objects.create(
                email=email,
                otp_code=otp_code,
                expires_at=expires_at
            )
            
            SignupSerializer.send_otp_email(email, otp_code)
            
            return self.success_response(
                {"email": email},
                message="OTP sent to email.",
                status_code=200
            )
        return self.error_response(
            "Resend OTP failed",
            status_code=400,
            data=serializer.errors
        )


class LoginView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            
            return self.success_response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "name": user.name,
                        "account_type": user.account_type,
                    }
                },
                message="Login successful.",
                status_code=200
            )
        return self.error_response(
            "Login failed",
            status_code=401,
            data=serializer.errors
        )


class ForgotPasswordView(StandardResponseMixin, APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            otp_code = ''.join(random.choices(string.digits, k=6))
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.filter(email=email, is_used=False).delete()
            OTP.objects.create(
                email=email,
                otp_code=otp_code,
                expires_at=expires_at
            )
            
            SignupSerializer.send_otp_email(email, otp_code)
            
            return self.success_response(
                {"email": email},
                message="OTP sent to email for password reset.",
                status_code=200
            )
        return self.error_response(
            "Forgot password failed",
            status_code=400,
            data=serializer.errors
        )


class ResetPasswordView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]  # user must be logged in via OTP verify token


    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user  # authenticated via token from VerifyOTPView
            new_password = serializer.validated_data['new_password']

            user.set_password(new_password)
            user.save(update_fields=['password', 'updated_at'])

            return self.success_response(
                message="Password reset successful.",
                status_code=200
            )
        return self.error_response(
            "Password reset failed",
            status_code=400,
            data=serializer.errors
        )


class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request}#added for image public url
        )
        if serializer.is_valid():
            user = serializer.save()

            #for image public url
            image_url=None
            if user.image:
                image_url=request.build_absolute_uri(user.image.url)

            return Response({
                "message": "Profile updated",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "contact_number": user.contact_number,
                    "image": image_url
                    # "account_type": user.account_type
                }
            })
        return Response(serializer.errors, status=400)


class DeleteUserView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = ConfirmDeleteUserSerializer(
            data=request.data,
            context={"request": request}
        )

        if not serializer.is_valid():
            return self.error_response(
                "Password verification failed",
                data=serializer.errors,
                status_code=400
            )

        request.user.delete()

        # 204 = no response body
        # return Response(status=status.HTTP_204_NO_CONTENT)
        return self.success_response(
            message="Your account has been deleted successfully.",
            status_code=200,
            data=None
        )



class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user,context={"request": request})#added for image public url)
        return Response(serializer.data, status=200)



class AccountTypeSetupView(StandardResponseMixin, APIView):
    """
    Set account type after OTP verification.
    Required before user can access main features.
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        # Check if account type is already set
        if request.user.account_type:
            return self.error_response(
                "Account type is already configured.",
                status_code=400
            )
        
        serializer = AccountTypeSelectionSerializer(
            instance=request.user,
            data=request.data
        )
        
        if serializer.is_valid():
            user = serializer.save()
            
            return self.success_response(
                data={
                    "account_type": user.account_type,
                    "staff_limit": user.staff_limit
                },
                message="Account setup completed successfully.",
                status_code=200
            )
        
        return self.error_response(
            "Account setup failed",
            status_code=400,
            data=serializer.errors
        )


class SubUserListCreateView(StandardResponseMixin, APIView):
    """
    List all staff members or create new staff.
    Only for salon_owner_with_staff account type.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all staff members for the salon owner"""
        user = request.user
        # Check if user can have staff
        if user.account_type != 'salon_owner_with_staff':
            return self.error_response(
                "Your account type does not support staff management,only salon owners with staff can manage sub-users",
                status_code=403
            )
        
        # Check staff limit
        # current_staff_count = user.sub_users.filter(is_active=True).count()
        # if current_staff_count >= user.staff_limit:
        #     return self.error_response(
        #         f"Staff limit reached ({user.staff_limit})",
        #         status_code=400
        #     )
        
        # Get all staff with optimized query
        # sub_users = request.user.sub_users.all().order_by('-created_at')
        sub_users = user.sub_users.filter(is_active=True).select_related('main_user').order_by('-created_at')
        serializer = SubUserSerializer(sub_users, many=True)
        
        return self.success_response(
            data={
                "staff_members": serializer.data,
                "total_staff": sub_users.count(),#I removed len(serializer.data) so that avoids building full list just to count.
                "staff_limit": request.user.staff_limit,
                "can_add_more": request.user.can_add_staff()
            },
            message="Staff list(Sub-users) retrieved successfully",
            status_code=200
        )
    
    @transaction.atomic
    def post(self, request):
        """Create new staff member"""
        user = request.user
        # Check if user can have staff
        if user.account_type != 'salon_owner_with_staff':
            return self.error_response(
                "Your account type does not support staff management.",
                status_code=403
            )
        
        # Check staff limit
        if not user.can_add_staff():
            return self.error_response(
                f"You have reached your staff limit of {request.user.staff_limit}.",
                status_code=400
            )
        
        serializer = SubUserCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            sub_user = serializer.save()
            
            response_serializer = SubUserInviteResponseSerializer(sub_user)

            return Response({
                "success": True,
                "statusCode": 201,
                "message": "Staff member created successfully",
                "data": response_serializer.data
            })
            # return self.success_response(
            #     data=SubUserSerializer(sub_user).data,
            #     message="Staff member created successfully",
            #     status_code=201
            # )
        
        return self.error_response(
            "Failed to create staff member",
            status_code=400,
            data=serializer.errors
        )


class SubUserDetailView(StandardResponseMixin, APIView):
    """
    Retrieve, update, or delete a specific staff member.
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, request, sub_user_id):
        """Get sub-user if it belongs to the requesting user"""
        try:
            return request.user.sub_users.get(id=sub_user_id)
        except SubUser.DoesNotExist:
            return None
    
    def get(self, request, sub_user_id):
        """Get staff member details"""
        sub_user = self.get_object(request, sub_user_id)
        
        if not sub_user:
            return self.error_response(
                "Staff member not found",
                status_code=404
            )
        
        serializer = SubUserSerializer(sub_user)
        
        return self.success_response(
            data=serializer.data,
            message="Staff member retrieved successfully",
            status_code=200
        )
    
    @transaction.atomic
    def patch(self, request, sub_user_id):
        """Update staff member information"""
        sub_user = self.get_object(request, sub_user_id)
        
        if not sub_user:
            return self.error_response(
                "Staff member not found",
                status_code=404
            )
        
        serializer = SubUserSerializer(
            sub_user,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            sub_user = serializer.save()
            
            return self.success_response(
                data=SubUserSerializer(sub_user).data,
                message="Staff member updated successfully",
                status_code=200
            )
        
        return self.error_response(
            "Failed to update staff member",
            status_code=400,
            data=serializer.errors
        )
    
    @transaction.atomic
    def delete(self, request, sub_user_id):
        """Delete (deactivate) staff member"""
        sub_user = self.get_object(request, sub_user_id)
        
        if not sub_user:
            return self.error_response(
                "Staff member not found",
                status_code=404
            )
        
        # Soft delete by marking as inactive
        sub_user.is_active = False
        sub_user.save(update_fields=['is_active', 'updated_at'])
        
        return self.success_response(
            message="Staff member deactivated successfully",
            status_code=200
        )
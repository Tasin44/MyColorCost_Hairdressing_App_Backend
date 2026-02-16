

from rest_framework import serializers
from .models import User, SubUser, OTP
from affiliateapp.models import Referral,ReferralCode

# serializers.py
from rest_framework import serializers
from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import random
import string
from .utils import validate_and_get_otp


# class AccountTypeSelectionSerializer(serializers.Serializer):
#     account_type = serializers.ChoiceField(
#         # choices=[
#         #     ('salon_owner_with_staff', 'Salon Owner with Staff'),
#         #     ('self_employed', 'Self-employed Hairdresser'),
#         # ]
#         choices=User.ACCOUNT_TYPE_CHOICES
#     )
#     staff_limit = serializers.IntegerField(min_value=0, default=0, required=False)

#     def validate(self, data):
#         account_type = data['account_type']
#         staff_count = data.get('staff_limit', 0)
        
#         if account_type == 'salon_owner_with_staff' and staff_count <=0:
#             raise serializers.ValidationError(
#                 {"staff_count": "Staff count is required for salon owner with staff."}
#             )
#         return data #❌Without this return , I got error : AssertionError: .validate() should return the validated data, because validate(self, data) → must return data
#     #❓❓ why using update() here?
#     '''
#     validate() method references staff_count = data.get('staff_limit', 0) but you also pass staff_limit in serializer. Make sure this doesn’t conflict with save() method.

#     Currently, serializer.save() in AccountTypeSetupView won’t actually save anything unless you define update() method in serializer. So user.account_type may remain None.
#     '''
#     def update(self, instance, validated_data):
#         instance.account_type = validated_data['account_type']
#         instance.staff_limit = validated_data.get('staff_limit', 0)
#         instance.save()
#         return instance

class SignupSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    email = serializers.EmailField()
    owner_email = serializers.EmailField(required=False)# only for staff
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(required=True)
    contact_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    google_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    google_signup = serializers.BooleanField(default=False)
    referral_code = serializers.CharField(
        max_length=10,
        required=False,
        allow_blank=True,
        help_text="Optional referral code"
    )
    
    # ...existing code...
    
    def validate_email(self, value):
        value = value.lower().strip()
        verified_user = User.objects.filter(email=value, verified=True).exists()
        if verified_user:
            raise serializers.ValidationError("This email is already registered.")
        return value
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        role = self.context.get("role")

        if role in ['staff', 'retailer']:
            data.pop('account_type', None)

        return data
    
    def validate(self, data):
        role = data['role']

        if role == 'staff':
            if not data.get('owner_email'):
                raise serializers.ValidationError({"owner_email": "Owner email is required for staff."})
            # existing owner_email validation...
        
        if role == 'retailer':
            # Retailer signup, no owner needed
            pass

        # Google signup validation
        if data.get('google_signup') and not data.get('google_id'):
            raise serializers.ValidationError(
                {"google_id": "Google ID is required for Google signup."}
            )
        
        # Staff registration validation (only if owner_email exists)
        if 'owner_email' in data and 'email' in data:
            owner_email = data.get('owner_email').lower().strip()
            staff_email = data.get('email').lower().strip()

            try:
                #owner = User.objects.get(email=owner_email, account_type='salon_owner_with_staff')
                owner = User.objects.get(email=owner_email, role='owner')
            except User.DoesNotExist:
                raise serializers.ValidationError({"owner_email": "Owner not found."})

            # Check if staff is pre-registered
            try:
                sub_user = SubUser.objects.get(main_user=owner, email=staff_email, status='PENDING')
            except SubUser.DoesNotExist:
                raise serializers.ValidationError({"email": "This staff email is not registered for the owner."})

            '''
            ❌❌❌
            Staff limit should ONLY be enforced when OWNER creates staff slots
                Because:
                Owner already reserved the slot
                Staff signup should just claim their reserved slot
            '''
            # Check staff limit❌
            # if owner.get_staff_count() >= owner.staff_limit:
            #     raise serializers.ValidationError({"owner": "Owner's staff limit reached."})

            data['sub_user'] = sub_user
            data['owner'] = owner
        
        return data
    def validate_referral_code(self, value):
        """Validate referral code if provided"""
        if value and value.strip():
            value = value.strip().upper()
            try:
                ReferralCode.objects.get(code=value)
            except ReferralCode.DoesNotExist:
                raise serializers.ValidationError("Invalid referral code")
        return value if value else None
    
    #previous create method which was working vefore affiliate
    '''
    def create(self, validated_data):
        role = validated_data['role']
        email = validated_data['email']
        name = validated_data.get("name", "").strip()
        contact_number = validated_data.get('contact_number', '')
        google_signup = validated_data.get('google_signup', False)
        google_id = validated_data.get('google_id')
        
        # Delete old unverified accounts
        User.objects.filter(email=email, verified=False).delete()
        
        # Create user based on signup type
        if validated_data.get('google_signup', False):
            user = User.objects.create_user(
                username=email,
                email=email,
                password=None,  # No password for Google signup
                name=name,
                contact_number=contact_number,
                google_id=google_id
            )
        else:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=validated_data['password'],
                name=name,
                contact_number=contact_number
            )
        user.role = role
        user.save(update_fields=['role'])

        if role == 'staff':
            #✅ This ensures pre-registered staff becomes active and linked to a user.
            sub_user = validated_data['sub_user']  # This comes from your validate()
            # sub_user.user = user  # link FK (you need to add FK field in SubUser model if not yet)
            # sub_user.status = 'ACTIVE'
            # sub_user.save()
            sub_user.user = user
            sub_user.name = name
            sub_user.contact_number = contact_number
            sub_user.status = 'ACTIVE'
            # sub_user.is_active = True
            sub_user.save()
        # Generate and send OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTP.objects.filter(email=email, is_used=False).delete()
        OTP.objects.create(
            email=email,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        self.send_otp_email(email, otp_code)
        self.context['otp'] = otp_code
        return user
    '''
    @transaction.atomic
    def create(self, validated_data):
        role = validated_data['role']
        email = validated_data['email']
        name = validated_data.get("name", "").strip()
        contact_number = validated_data.get('contact_number', '')
        google_signup = validated_data.get('google_signup', False)
        google_id = validated_data.get('google_id')
        referral_code_str = validated_data.pop('referral_code', None)
        
        # Delete old unverified accounts
        User.objects.filter(email=email, verified=False).delete()
        
        # Create user based on signup type
        if google_signup:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=None,  # No password for Google signup
                name=name,
                contact_number=contact_number,
                google_id=google_id
            )
        else:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=validated_data['password'],
                name=name,
                contact_number=contact_number
            )
        
        user.role = role
        user.save(update_fields=['role'])
        
        # ✅ Handle staff linking
        if role == 'staff':
            sub_user = validated_data['sub_user']
            sub_user.user = user
            sub_user.name = name
            sub_user.contact_number = contact_number
            sub_user.status = 'ACTIVE'
            sub_user.save()
        
        # ✅ Generate unique referral code for new user
        import secrets
        import string
        
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        while ReferralCode.objects.filter(code=code).exists():
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        
        ReferralCode.objects.create(user=user, code=code)
        
        # ✅ Track referral if code was provided
        if referral_code_str:
            try:
                referral_code = ReferralCode.objects.get(code=referral_code_str)
                from .models import Referral  # Import here to avoid circular import
                
                Referral.objects.create(
                    referrer=referral_code.user,
                    referred_user=user,
                    referral_code=referral_code,
                    status='pending'  # Will become 'active' when user subscribes
                )
            except ReferralCode.DoesNotExist:
                pass  # Already validated, but safety check
        
        # ✅ Generate and send OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTP.objects.filter(email=email, is_used=False).delete()
        OTP.objects.create(
            email=email,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        self.send_otp_email(email, otp_code)
        self.context['otp'] = otp_code
        
        return user

    '''
    ❓From where this 'validated_data' comes in the line def create(self, validated_data)?
    Ans:
    When DRF serializer’s .is_valid() runs successfully, it stores cleaned input data in validated_data.
    DRF automatically passes this dictionary into the create() method when .save() is called.
    👉 In short: validated_data = all the valid fields from the user’s request (after passing validation).
    
    '''


    '''
    ❓Why @staticmethod for send_otp_email?
    Ans:
    @staticmethod: Means the method doesn't need access to self (the serializer instance),or any instance data. It's a utility function that can work independently
    Use case: The method only uses the parameters passed to it (email and otp_code)

    ❓why I can use a independant function like send_otp_email in this case

    🔴email and otp_code are generated by your system inside the create() method — not sent by the user.
    🔴Since send_otp_email() just uses those values to send an email, it doesn’t need anything from the serializer instance (self).
    🔴That’s why it can be a @staticmethod — it works independently of the serializer object.
    '''
    @staticmethod
    def send_otp_email(email, otp_code):
        subject = "Your OTP Code for Verification in Fixa"
        message = f"Your OTP code is: {otp_code}\nValid for 10 minutes."
        send_mail(subject, message, 'noreply@yourdomain.com', [email])


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, data):
        email = data['email'].lower().strip()
        otp_code = data['otp_code'].strip()
        otp = validate_and_get_otp(email, otp_code)  # 👈 call the function here

        data['otp'] = otp
        return data


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        value = value.lower().strip()
        user = User.objects.filter(email=value, verified=False).exists()
        if not user:
            raise serializers.ValidationError("No pending verification for this email.")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False)
    google_id = serializers.CharField(max_length=255, required=False)
    
    def validate(self, data):
        email = data['email'].lower().strip()
        password = data.get('password')
        google_id = data.get('google_id')
        
        try:
            user = User.objects.get(email=email, verified=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or user not verified.")
        
        # Check login method
        if google_id:
            if user.google_id != google_id:
                raise serializers.ValidationError("Invalid Google login.")
        else:
            if not password:
                raise serializers.ValidationError("Password is required for email login.")
            if not user.check_password(password):
                raise serializers.ValidationError("Invalid password.")
        
        data['user'] = user
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        value = value.lower().strip()
        user = User.objects.filter(email=value, verified=True).exists()
        if not user:
            raise serializers.ValidationError("Email not found or not verified.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    # email = serializers.EmailField()
    # otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)



class ProfileUpdateSerializer(serializers.ModelSerializer):
    # image=serializers.SerializerMethodField()
    image = serializers.ImageField(required=False)
    class Meta:
        model = User
        fields = ["name", "image","contact_number"]

    # def get_image(self,obj):
    #     request = self.context.get("request")
    #     if obj.image and request:
    #         return request.build_absolute_uri(obj.image.url)
    #     return None
'''
class DeleteUserSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "You must confirm account deletion."
            )
        return value
'''
class ConfirmDeleteUserSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value



class MeSerializer(serializers.ModelSerializer):
    sub_users_count = serializers.SerializerMethodField()
    can_create_staff = serializers.SerializerMethodField()
    image=serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'image', 'contact_number','role',
             'staff_limit', 'notification_enabled',
            'verified', 'sub_users_count', 'can_create_staff',
            'created_at'
        ]
    
    def get_sub_users_count(self, obj):
        # if obj.account_type == 'salon_owner_with_staff':
        if obj.role == 'owner':  # ✅ Changed
            return obj.sub_users.filter(is_active=True).count()
        return 0
    
    def get_can_create_staff(self, obj):
        # if obj.account_type == 'salon_owner_with_staff':
        if obj.role == 'owner':  # ✅ Changed
            current_staff_count = obj.sub_users.filter(is_active=True).count()
            return current_staff_count < obj.staff_limit
        return False
    
    def get_image(self,obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

class SubUserInviteResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubUser
        fields = ['id', 'email', 'is_active', 'created_at']


class SubUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubUser
        fields = ['id', 'name', 'contact_number', 'email', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class SubUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubUser
        # fields = ['name', 'email', 'contact_number']
        fields = ['email'] #only email will inputed by owner during registering a staff
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        main_user = self.context['request'].user

        if not main_user.can_add_staff():
            raise serializers.ValidationError("Only salon owners with staff can create sub-users")

        if main_user.sub_users.count() >= main_user.staff_limit:#related_name='sub_users'
            raise serializers.ValidationError("Staff limit reached")

        '''
        🔴🔴🔴When owner adds staff from dashboard, do not require password
        Status = PENDING, password = None
        '''
        subuser = SubUser.objects.create(
            main_user=main_user,
            status='PENDING',
            **validated_data# only name, email, contact_number
        )
        # subuser.password = make_password(validated_data['password'])#🔴🔴🔴Remove make_password() for now — the password will be set later by staff during signup.
        subuser.save()
        return subuser



class TeamSetupSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()  # ✅ Changed to UUIDField
    staff_limit = serializers.IntegerField(min_value=0)
    staff_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True
    )
    
    def validate_user_id(self, value):
        try:
            user = User.objects.get(id=value, role='owner', verified=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Owner user not found or not verified.")
        
        if user.staff_limit is not None and user.staff_limit > 0:
            raise serializers.ValidationError("Team setup already completed for this owner.")
        
        return value
    
    def validate(self, data):
        staff_emails = data.get('staff_emails', [])
        staff_limit = data['staff_limit']
        
        # Validate staff emails count
        if len(staff_emails) > staff_limit:
            raise serializers.ValidationError(
                {"staff_emails": f"Cannot add more than {staff_limit} staff emails."}
            )
        
        # Check for duplicate emails
        if len(staff_emails) != len(set(staff_emails)):
            raise serializers.ValidationError(
                {"staff_emails": "Duplicate staff emails are not allowed."}
            )
        
        # Validate staff emails don't conflict with existing users
        for staff_email in staff_emails:
            staff_email = staff_email.lower().strip()
            if User.objects.filter(email=staff_email, verified=True).exists():
                raise serializers.ValidationError(
                    {"staff_emails": f"Email {staff_email} is already registered."}
                )
        
        return data
    
    @transaction.atomic
    def save(self):
        user_id = self.validated_data['user_id']
        staff_limit = self.validated_data['staff_limit']
        staff_emails = self.validated_data.get('staff_emails', [])
        
        user = User.objects.get(id=user_id)
        user.staff_limit = staff_limit
        user.save(update_fields=['staff_limit'])
        
        # Create pre-registered staff entries
        created_staff = []
        for staff_email in staff_emails:
            staff_email = staff_email.lower().strip()
            sub_user = SubUser.objects.create(
                main_user=user,
                email=staff_email,
                name="",  # Will be set when staff signs up
                status='PENDING'
            )
            created_staff.append({
                "email": sub_user.email,
                "status": sub_user.status
            })
        
        return {
            "user_id": str(user.id),
            "staff_limit": user.staff_limit,
            "pre_registered_staff": created_staff
        }







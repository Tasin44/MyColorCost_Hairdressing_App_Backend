# clientapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.db import transaction
from django.db.models import Q, Count, Sum, Max
from django.utils import timezone
from datetime import timedelta

from .models import Client, ClientImage
from .serializers import (
    ClientListSerializer, ClientDetailSerializer,
    ClientCreateUpdateSerializer, ClientImageSerializer,
    ClientImageUploadSerializer, ClientStatsSerializer
)


class StandardResponseMixin:
    """Mixin for consistent API responses"""
    
    def success_response(self, data=None, message="Success", status_code=200):
        return Response({
            "success": True,
            "statusCode": status_code,
            "message": message,
            "data": data
        }, status=status_code)
    
    def error_response(self, message, status_code=400, data=None):
        return Response({
            "success": False,
            "statusCode": status_code,
            "message": message,
            "data": data
        }, status=status_code)
    def serializer_error_response(self, errors, status_code=400):
        """Extract first real error from serializer.errors and use as message"""
        message = "Validation failed"
        for field, field_errors in errors.items():
            if field == 'non_field_errors':
                message = field_errors[0] if field_errors else message
                break
            else:
                error_text = field_errors[0] if field_errors else str(field_errors)
                message = f"{field}: {error_text}"
                break
        return self.error_response(message, status_code=status_code, data=errors)

class ClientListCreateView(StandardResponseMixin, APIView):
    """
    List all clients or create new client.
    
    Access rules:
    - Salon owner: sees ALL clients (own + staff clients)
    - Staff (sub-user): sees only THEIR OWN clients
    
    Optimized with select_related and prefetch_related to avoid N+1 queries.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Add this line

    def get_queryset(self, request):
        """
        Get clients based on user role.
        Optimized query with related data prefetching.
        """
        user = request.user
        
        # Base queryset with optimizations
        queryset = Client.objects.select_related(
            'user', 'sub_user'
        ).prefetch_related(
            'images', # Prefetch images to check existence
            'mixes',  # ✅ ADD THIS - prefetch mixes
            'appointments'  # ✅ ADD THIS - prefetch appointments
        )
        
        # Check if request is from sub-user (staff)
        # In a real app, you'd implement sub-user authentication
        # For now, we assume all requests are from main users
        
        # Salon owner sees all clients
        #queryset = queryset.filter(user=user)
        # ✅ FIX: Owner sees ALL clients (own + staff clients)
        if user.role == 'owner':
            # Owner sees all clients under their account
            queryset = queryset.filter(user=user)
        elif user.role == 'staff' and hasattr(user, 'staff_profile'):
            # Staff sees only their own clients
            staff_profile = user.staff_profile
            queryset = queryset.filter(
                user=staff_profile.main_user,  # Owner's clients
                sub_user=staff_profile  # Only this staff's clients
            )
        else:
            # Fallback: show user's own clients()
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def get(self, request):
        """
        Get list of clients with optional filtering and search.
        
        Query params:
        - search: Search by name, email, or contact
        - service_type: Filter by service type
        - has_appointment: Filter clients with upcoming appointments
        - recent: Show only recent clients (last 30 days)
        """
        queryset = self.get_queryset(request)
        
        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(contact_number__icontains=search)
            )
        
        # Filter by service type
        service_type = request.query_params.get('service_type', '').strip()
        if service_type:
            queryset = queryset.filter(service_type__iexact=service_type)
        
        # Filter clients with upcoming appointments
        has_appointment = request.query_params.get('has_appointment')
        if has_appointment == 'true':
            queryset = queryset.filter(
                next_appointment_date__gte=timezone.now().date()
            )
        
        # Filter recent clients
        recent = request.query_params.get('recent')
        if recent == 'true':
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(created_at__gte=thirty_days_ago)
        
        # Order by most recent
        queryset = queryset.order_by('-created_at')
        
        # Serialize
        serializer = ClientListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        
        return self.success_response(
            data={
                'clients': serializer.data,
                'total_count': queryset.count()
            },
            message="Clients retrieved successfully",
            status_code=200
        )
    
    @transaction.atomic
    def post(self, request):
        """
        Create new client.
        Previoulsy -Client is associated with the logged-in user (salon owner).
        Now- Client is associated with the owner, but tracks which staff created it.
        """
        serializer = ClientCreateUpdateSerializer(data=request.data,context={'request': request})
        
        if serializer.is_valid():
            user = request.user
            
            # ✅ FIX: Determine owner and sub_user based on role
            if user.role == 'staff' and hasattr(user, 'staff_profile'):
                # Staff creating client
                staff_profile = user.staff_profile
                owner = staff_profile.main_user
                sub_user = staff_profile
            else:
                # Owner creating client
                owner = user
                sub_user = None

            # Create client and associate with user
            client = serializer.save(
                user=owner,      # ✅ Use owner, not request.user
                sub_user=sub_user  # ✅ Use calculated sub_user
            )
            '''
            client = serializer.save(
                user=request.user,
                sub_user=None  # Set if request is from staff
            )  
            '''
   
            # Return detailed client data
            detail_serializer = ClientDetailSerializer(
                client,
                context={'request': request}
            )
            
            return self.success_response(
                data=detail_serializer.data,
                message="Client created successfully",
                status_code=201
            )
        
        # return self.error_response(
        #     "Failed to create client",
        #     status_code=400,
        #     data=serializer.errors
        # )
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED


class ClientDetailView(StandardResponseMixin, APIView):
    """
    Retrieve, update, or delete a specific client.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Add this line
    '''
    def get_object(self, request, client_id):
        """
        Get client if user has access.
        Optimized with select_related and prefetch_related.
        """
        try:
            # Owner sees all clients
            client = Client.objects.select_related(
                'user', 'sub_user'
            ).prefetch_related(
                'images',
                'mixes__mix_products'
            ).get(
                id=client_id,
                user=request.user
            )
            return client
        except Client.DoesNotExist:
            return None
    '''
    def get_object(self, request, client_id):
        """
        Get client if user has access.
        Staff can access their own clients, owner can access all.
        """
        user = request.user
        
        try:
            if user.role == 'staff' and hasattr(user, 'staff_profile'):
                # Staff can only access their own clients
                staff_profile = user.staff_profile
                client = Client.objects.select_related(
                    'user', 'sub_user'
                ).prefetch_related(
                    'images',
                    'mixes__mix_products'
                ).get(
                    id=client_id,
                    user=staff_profile.main_user,  # Owner's client
                    sub_user=staff_profile  # But created by this staff
                )
            else:
                # Owner can access all clients
                client = Client.objects.select_related(
                    'user', 'sub_user'
                ).prefetch_related(
                    'images',
                    'mixes__mix_products'
                ).get(
                    id=client_id,
                    user=user  # Owner's clients
                )
            
            return client
            
        except Client.DoesNotExist:
            return None
    
    def get(self, request, client_id):
        """Get client details including images and mix history"""
        client = self.get_object(request, client_id)
        
        if not client:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        
        serializer = ClientDetailSerializer(
            client,
            context={'request': request}
        )
        
        return self.success_response(
            data=serializer.data,
            message="Client retrieved successfully",
            status_code=200
        )
    
    @transaction.atomic
    def patch(self, request, client_id):
        """Update client information"""

        client = self.get_object(request, client_id)
        
        if not client:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        
        serializer = ClientCreateUpdateSerializer(
            client,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        # serializer = ClientCreateUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            client = serializer.save()
            
            detail_serializer = ClientDetailSerializer(
                client,
                context={'request': request}
            )
            
            return self.success_response(
                data=detail_serializer.data,
                message="Client updated successfully",
                status_code=200
            )
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
        '''
        return self.error_response(
            "Failed to update client",
            status_code=400,
            data=serializer.errors
        )
        '''

    
    @transaction.atomic
    def delete(self, request, client_id):
        """
        Delete client.
        This will cascade delete all related data (images, mixes, etc.)
        """
        client = self.get_object(request, client_id)
        
        if not client:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        
        client_name = client.name
        client.delete()
        
        return self.success_response(
            message=f"Client '{client_name}' deleted successfully",
            status_code=200
        )


class ClientImageUploadView(StandardResponseMixin, APIView):
    """
    Upload before/after images for a client.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_client(self, request, client_id):
        """Get client if user has access"""
        try:
            return Client.objects.get(id=client_id, user=request.user)
        except Client.DoesNotExist:
            return None
    
    @transaction.atomic
    def post(self, request, client_id):
        """
        Upload client image (before or after photo).
        
        Required fields:
        - image: Image file
        - image_type: 'before' or 'after'
        """
        client = self.get_client(request, client_id)
        
        if not client:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        
        serializer = ClientImageUploadSerializer(data=request.data)
        
        if serializer.is_valid():
            # Save image associated with client
            # image = serializer.save(client=client)
            
            # # Return image data
            # image_serializer = ClientImageSerializer(
            #     image,
            #     context={'request': request}
            # )
            files = request.FILES.getlist('image')
            if not files:
                return Response(
                    {"error": "No images provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            created_images = []

            for file in files:
                img = ClientImage.objects.create(
                    client=client,
                    image=file,
                    image_type=request.data.get('image_type')
                )
                created_images.append(img)  
            serializer=ClientImageSerializer(created_images, many=True , context={"request": request})
            return self.success_response(
                data=serializer.data,
                message="Image uploaded successfully",
                status_code=201
            )
        return self.serializer_error_response(serializer.errors)  # ✅ CHANGED
        # return self.error_response(
        #     "Failed to upload image",
        #     status_code=400,
        #     data=serializer.errors
        # )


class ClientImageListView(StandardResponseMixin, APIView):
    """
    Get all images for a specific client.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, client_id):
        """Get all images (before and after) for a client"""
        try:
            client = Client.objects.get(id=client_id, user=request.user)
        except Client.DoesNotExist:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        
        # Get images ordered by upload date
        images = client.images.order_by('-upload_date')
        
        # Separate by type
        before_images = images.filter(image_type='before')
        after_images = images.filter(image_type='after')
        
        serializer_context = {'request': request}
        
        return self.success_response(
            data={
                'before_images': ClientImageSerializer(
                    before_images, 
                    many=True, 
                    context=serializer_context
                ).data,
                'after_images': ClientImageSerializer(
                    after_images, 
                    many=True, 
                    context=serializer_context
                ).data,
                'total_images': images.count()
            },
            message="Client images retrieved successfully",
            status_code=200
        )


class ClientImageDeleteView(StandardResponseMixin, APIView):
    """
    Delete a specific client image.
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def delete(self, request, client_id, image_id):
        """Delete client image"""
        try:
            # Verify client belongs to user
            client = Client.objects.get(id=client_id, user=request.user)
            
            # Get image
            image = ClientImage.objects.get(id=image_id, client=client)
            
            # Delete image file and database entry
            image.image.delete()  # Delete file from storage
            image.delete()  # Delete database entry
            
            return self.success_response(
                message="Image deleted successfully",
                status_code=200
            )
            
        except Client.DoesNotExist:
            return self.error_response(
                "Client not found",
                status_code=404
            )
        except ClientImage.DoesNotExist:
            return self.error_response(
                "Image not found",
                status_code=404
            )


class ClientStatsView(StandardResponseMixin, APIView):
    """
    Get client statistics for dashboard.
    Optimized with aggregation queries.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get aggregated client statistics"""
        user = request.user
        
        # Get current date ranges
        now = timezone.now()
        first_day_of_month = now.replace(day=1).date()
        three_months_ago = (now - timedelta(days=90)).date()
        
        # Get all clients for user
        all_clients = Client.objects.filter(user=user)
        
        # Aggregate statistics
        stats = {
            'total_clients': all_clients.count(),
            'clients_this_month': all_clients.filter(
                created_at__gte=first_day_of_month
            ).count(),
            'clients_with_appointments': all_clients.filter(
                next_appointment_date__gte=now.date()
            ).count(),
            'total_mixes_all_clients': all_clients.aggregate(
                total=Sum('total_mixes')
            )['total'] or 0,
            'active_clients': all_clients.filter(
                last_visit_date__gte=three_months_ago
            ).count()
        }
        
        serializer = ClientStatsSerializer(data=stats)
        serializer.is_valid()
        
        return self.success_response(
            data=serializer.data,
            message="Client statistics retrieved successfully",
            status_code=200
        )
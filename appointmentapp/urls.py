# appointmentapp/urls.py

from django.urls import path
from .views import (
    WorkingHoursSetupView,
    AppointmentURLGenerateView,
    AvailableTimeSlotsView,
    AppointmentCreateView,
    AppointmentSelfBookingView,
    AppointmentListView,
    TodayAppointmentsView,
    AppointmentDetailView,
    AppointmentStatsView,
    CleanupOldSlotsView,
    DashboardStatsView
)

app_name = 'appointment'

urlpatterns = [
    # ==================== SETUP ENDPOINTS ====================
    
    # Set working hours (one-time setup)
    # POST /appointment/working-hours/setup/
    # GET /appointment/working-hours/setup/
    path('working-hours/setup/', WorkingHoursSetupView.as_view(), name='working-hours-setup'),
    
    # Generate appointment URL for client booking (one-time)
    # POST /appointment/generate-url/
    # GET /appointment/generate-url/
    path('generate-url/', AppointmentURLGenerateView.as_view(), name='generate-url'),
    
    # ==================== AVAILABILITY ====================
    
    # Get available time slots for a date
    # GET /appointment/available-slots/?date=2024-12-25
    # Optional: &user_id=xxx (for client self-booking)
    path('available-slots/', AvailableTimeSlotsView.as_view(), name='available-slots'),
    
    # ==================== MANUAL APPOINTMENT CREATION ====================
    
    # Create appointment manually (by owner/staff)
    # POST /appointment/create/
    path('create/', AppointmentCreateView.as_view(), name='create'),
    
    # ==================== CLIENT SELF-BOOKING ====================
    
    # Client self-booking endpoint (no auth required)
    # GET /appointment/book/{token}/ - Get booking page info
    # POST /appointment/book/{token}/ - Create appointment
    path('book/<str:token>/', AppointmentSelfBookingView.as_view(), name='self-booking'),
    
    # ==================== APPOINTMENT MANAGEMENT ====================
    
    # List appointments with filtering
    # GET /appointment/list/
    # Query params: ?date=2024-12-25&status=scheduled&today=true&upcoming=true
    path('list/', AppointmentListView.as_view(), name='list'),
    
    # Get today's appointments (for home page)
    # GET /appointment/today/
    path('today/', TodayAppointmentsView.as_view(), name='today'),
    
    # Get appointment details
    # GET /appointment/{appointment_id}/
    path('<int:appointment_id>/', AppointmentDetailView.as_view(), name='detail'),
    
    # Update appointment (status, notes)
    # PATCH /appointment/{appointment_id}/
    path('<int:appointment_id>/', AppointmentDetailView.as_view(), name='update'),
    
    # Cancel/delete appointment
    # DELETE /appointment/{appointment_id}/
    path('<int:appointment_id>/', AppointmentDetailView.as_view(), name='delete'),
    
    # ==================== STATISTICS ====================
    
    # Get appointment statistics
    # GET /appointment/stats/
    path('stats/', AppointmentStatsView.as_view(), name='stats'),
    
    # ==================== ADMIN/MAINTENANCE ====================
    
    # Cleanup old time slot bookings (cron job)
    # POST /appointment/cleanup-slots/
    path('cleanup-slots/', CleanupOldSlotsView.as_view(), name='cleanup-slots'),

    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
]

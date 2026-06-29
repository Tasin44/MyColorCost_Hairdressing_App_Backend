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
    DashboardStatsView,
    BookingPageView
)
from .new_views import (
    ServiceListView,
    ServiceDetailView,
    NewWorkingHoursSetupView,
    NewAppointmentCreateView,
    CancelAppointmentView,
    NewSelfBookingView,
    NewAvailableTimeSlotsView,
    NewBookingPageView,
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

    # 1. HTML Booking Page (must come FIRST)
    path('book/<str:token>/', BookingPageView.as_view(), name='booking-page'),

    # Client self-booking endpoint (no auth required)
    # GET /appointment/book/{token}/ - Get booking page info
    # POST /appointment/book/{token}/ - Create appointment
    #path('book/<str:token>/', AppointmentSelfBookingView.as_view(), name='self-booking'),
    path('book/<str:token>/data/', AppointmentSelfBookingView.as_view(), name='booking-data'),
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


   # path('book/<str:token>/', BookingPageView.as_view(), name='booking-page'),


    # =========================================================
    # NEW API ENDPOINTS  (existing endpoints above are untouched)
    # =========================================================

    # Service management (Settings → Services)
    path('services/', ServiceListView.as_view(), name='service-list'),
    path('services/<int:service_id>/', ServiceDetailView.as_view(), name='service-detail'),

    # Per-day working hours (new flexible setup)
    path('working-hours/setup/new/', NewWorkingHoursSetupView.as_view(), name='new-working-hours-setup'),

    # New appointment creation (supports multiple services + extra times)
    path('create/new/', NewAppointmentCreateView.as_view(), name='new-appointment-create'),
    path('create/new/<int:appointment_id>/', NewAppointmentCreateView.as_view(), name='new-appointment-detail'),

    # Cancel appointment — frees the time slot back to available
    # DELETE /appointment/create/new/<id>/
    path('create/new/<int:appointment_id>/cancel/', CancelAppointmentView.as_view(), name='new-appointment-cancel'),

    # New client self-booking (returns enriched service details)
    path('book/<str:token>/new/', NewBookingPageView.as_view(), name='new-booking-page'),
    path('book/<str:token>/new', NewBookingPageView.as_view()),
    path('book/<str:token>/new/data/', NewSelfBookingView.as_view(), name='new-self-booking'),

    # New available time slots (aware of DailyWorkingHours)
    path('available-slots/new/', NewAvailableTimeSlotsView.as_view(), name='new-available-slots'),
]

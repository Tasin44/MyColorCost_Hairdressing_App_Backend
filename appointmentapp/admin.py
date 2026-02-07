from django.contrib import admin

# Register your models here.
from .models import Appointment,TimeSlotBooking,AppointmentURL,WorkingHours,ServiceType

# Register your models here.
admin.site.register(Appointment)
admin.site.register(TimeSlotBooking)
admin.site.register(AppointmentURL)
admin.site.register(WorkingHours)
admin.site.register(ServiceType)

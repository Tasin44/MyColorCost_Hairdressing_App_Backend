from django.contrib import admin

# Register your models here.
from .models import Appointment,TimeSlotBooking,AppointmentURL,WorkingHours,ServiceType,DailyWorkingHours

# Register your models here.
admin.site.register(Appointment)
admin.site.register(TimeSlotBooking)
admin.site.register(AppointmentURL)
admin.site.register(WorkingHours)
admin.site.register(DailyWorkingHours)
admin.site.register(ServiceType)

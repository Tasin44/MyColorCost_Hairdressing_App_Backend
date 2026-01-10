from django.contrib import admin

# Register your models here.
from .models import User,OTP,SubUser

# Register your models here.
admin.site.register(User)
admin.site.register(SubUser)
admin.site.register(OTP)
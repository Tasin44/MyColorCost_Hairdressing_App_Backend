from django.contrib import admin

# Register your models here.
from .models import Client,ClientImage
# Register your models here.
admin.site.register(Client)
admin.site.register(ClientImage)

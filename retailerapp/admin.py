from django.contrib import admin

# Register your models here.
from .models import (
    RetailerProfile,
    DeliveryArea,
    MissingProduct,
    CustomerDeliveryAddress
)

# Register all models
admin.site.register(RetailerProfile)
admin.site.register(DeliveryArea)
admin.site.register(MissingProduct)
admin.site.register(CustomerDeliveryAddress)



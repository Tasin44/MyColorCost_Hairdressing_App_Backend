from django.contrib import admin
from .models import (
    ShopProduct, 
    UserProduct, 
    ShoppingCart, 
    ProductScanHistory, 
    ProductReview, 
    Mix, 
    MixProduct,
)

# Register all models
admin.site.register(ShopProduct)
admin.site.register(UserProduct)
admin.site.register(ShoppingCart)
admin.site.register(ProductScanHistory)
admin.site.register(ProductReview)
admin.site.register(Mix)
admin.site.register(MixProduct)
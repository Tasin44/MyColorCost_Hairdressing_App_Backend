# mixapp/urls.py
from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import (
    # Shop Products
    ShopProductListView, ShopProductDetailView,
 
    # User Products (Inventory)
    UserProductListView, UserProductDetailView,
 
    # Mixes
    CheckMixCreationView, MixListCreateView,
    MixDetailView, MixAddProductView,
    MixRemoveProductView, MixStatsView,
 
    # Reviews
    ProductReviewListView, UserReviewsView, MixGeneratePDFView,
    MixSetChargedAmountView,MixViewSet
)
 
app_name = 'mixapp'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'mixes', MixViewSet, basename='mix')
 
urlpatterns = [
    # Shop Products (Master Catalog)
    path('shop-products/', ShopProductListView.as_view(), name='shop-product-list'),
    path('shop-products/<int:product_id>/', ShopProductDetailView.as_view(), name='shop-product-detail'),
 
    # User Products (Inventory)
    path('inventory/', UserProductListView.as_view(), name='user-product-list'),
    path('inventory/<int:user_product_id>/', UserProductDetailView.as_view(), name='user-product-detail'),
 
    # Mix Creation Check
    path('mixes/check/', CheckMixCreationView.as_view(), name='check-mix-creation'),
 
    # Mixes
    path('mixes/', MixListCreateView.as_view(), name='mix-list-create'),
    path('mixes/<int:mix_id>/', MixDetailView.as_view(), name='mix-detail'),
    path('mixes/<int:mix_id>/add-product/', MixAddProductView.as_view(), name='mix-add-product'),
    path('mixes/<int:mix_id>/products/<int:mix_product_id>/', MixRemoveProductView.as_view(), name='mix-remove-product'),
 
    # Mix Statistics
    path('mixes/stats/', MixStatsView.as_view(), name='mix-stats'),
 
    # Product Reviews
    path('shop-products/<int:product_id>/reviews/', ProductReviewListView.as_view(), name='product-reviews'),
    path('my-reviews/', UserReviewsView.as_view(), name='user-reviews'),
    path("mixes/<int:mix_id>/generate-pdf/", MixGeneratePDFView.as_view()),

    path('mixes/<int:mix_id>/set-charge/', MixSetChargedAmountView.as_view(), name='mix-set-charge'),

    # ✅ Include router URLs
    path('', include(router.urls)),
]



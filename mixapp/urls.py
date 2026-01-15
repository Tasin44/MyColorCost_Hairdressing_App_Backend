# mixapp/urls.py
from django.urls import path
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
    ProductReviewListView, UserReviewsView
)
 
app_name = 'mixapp'
 
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
]



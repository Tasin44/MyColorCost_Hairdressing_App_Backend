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
    MixSetChargedAmountView,MixViewSet,
    
    # Barcode & Manual Entry
    ScanBarcodeView, ManualProductEntryView,
    UpdateScannedProductView,ProductScanHistoryView,
    AddToCartView, ViewCartView, RemoveFromCartView, UpdateCartItemView,
    ExpenseViewSet,RetailerProductsListView,UserInventoryProductsView,FinancialOverviewView
)
 
app_name = 'mixapp'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'mixes', MixViewSet, basename='mix')
router.register(r'expenses', ExpenseViewSet, basename='expense')  # ✅ ADD THIS

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
    path('scan-barcode/', ScanBarcodeView.as_view(), name='scan-barcode'),
    path('manual-product-entry/', ManualProductEntryView.as_view(), name='manual-product-entry'),
    path('update-scanned-product/<int:product_id>/', UpdateScannedProductView.as_view(), name='update-scanned-product'),  
    path('scan-history/', ProductScanHistoryView.as_view(), name='scan-history'),  # ✅ ADD THIS



    # Cart APIs
    path('cart/add/', AddToCartView.as_view(), name='add-to-cart'),
    path('cart/', ViewCartView.as_view(), name='view-cart'),
    path('cart/<int:cart_item_id>/', RemoveFromCartView.as_view(), name='remove-from-cart'),
    path('cart/<int:cart_item_id>/update/', UpdateCartItemView.as_view(), name='update-cart'),


    #=======================================================
    # ✅ NEW: Retailer products (for purchasing)
    path('retailer-products/', RetailerProductsListView.as_view(), name='retailer-products-list'),
    
    # ✅ NEW: User inventory (scanned + manual)
    path('user-inventory/', UserInventoryProductsView.as_view(), name='user-inventory'),

    #===========================================================
    path('financial-overview/', FinancialOverviewView.as_view(), name='financial-overview'),

]



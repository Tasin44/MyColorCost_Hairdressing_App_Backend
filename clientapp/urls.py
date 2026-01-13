# clientapp/urls.py
from django.urls import path
from .views import (
    ClientListCreateView, ClientDetailView,
    ClientImageUploadView, ClientImageListView,
    ClientImageDeleteView, ClientStatsView
)

app_name = 'clientapp'

urlpatterns = [
    # Client Management
    path('', ClientListCreateView.as_view(), name='client-list-create'),
    path('<int:client_id>/', ClientDetailView.as_view(), name='client-detail'),
    
    # Client Images
    path('<int:client_id>/images/', ClientImageListView.as_view(), name='client-images'),
    path('<int:client_id>/images/upload/', ClientImageUploadView.as_view(), name='client-image-upload'),
    path('<int:client_id>/images/<int:image_id>/', ClientImageDeleteView.as_view(), name='client-image-delete'),
    
    # Statistics
    path('stats/', ClientStatsView.as_view(), name='client-stats'),
]



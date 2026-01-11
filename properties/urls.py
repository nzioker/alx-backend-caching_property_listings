from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    # HTML views
    path('', views.PropertyListView.as_view(), name='property_list'),
    path('<uuid:pk>/', views.PropertyDetailView.as_view(), name='property_detail'),
    
    # API views
    path('api/', views.property_list_view, name='property_list_api'),
    path('api/list/', views.PropertyListAPIView.as_view(), name='property_list_api_v2'),
    path('api/stats/', views.CacheStatsView.as_view(), name='cache_stats'),
]

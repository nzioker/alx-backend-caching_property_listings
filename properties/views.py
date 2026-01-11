from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.views import APIView
import logging
from .models import Property
from .serializers import PropertySerializer
from .utils import get_all_properties, get_redis_cache_metrics
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# View-based caching
@cache_page(60 * 15)  # Cache for 15 minutes
@api_view(['GET'])
def property_list(request):
    """
    View-based caching for property list (15 minutes cache)
    """
    properties = Property.objects.all().order_by('-created_at')
    serializer = PropertySerializer(properties, many=True)
    
    # Add cache info to response
    response_data = {
        'count': properties.count(),
        'properties': serializer.data,
        'cached': True,
        'cache_timeout': 15 * 60,  # 15 minutes in seconds
        'cache_timestamp': cache.get('property_list_timestamp')
    }
    
    return JsonResponse(response_data)

# Class-based view with caching
@method_decorator(cache_page(60 * 15), name='dispatch')
class PropertyListView(ListView):
    model = Property
    template_name = 'properties/property_list.html'
    context_object_name = 'properties'
    paginate_by = 20
    
    def get_queryset(self):
        # Apply filters if any
        queryset = Property.objects.filter(is_available=True)
        
        # Filter by property type
        property_type = self.request.GET.get('property_type')
        if property_type:
            queryset = queryset.filter(property_type=property_type)
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        # Filter by price range
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['property_types'] = Property.PROPERTY_TYPES
        context['cache_info'] = {
            'is_cached': True,
            'timeout': 15,
            'metric': 'minutes'
        }
        return context

# REST API View with caching
class PropertyListAPIView(generics.ListAPIView):
    serializer_class = PropertySerializer
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(cache_page(60 * 15))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        # Use utility function for queryset caching
        return get_all_properties()

# Property detail view with caching
@cache_page(60 * 60)  # Cache for 1 hour
class PropertyDetailView(DetailView):
    model = Property
    template_name = 'properties/property_detail.html'
    context_object_name = 'property'
    
    def get_object(self):
        # Try to get from cache first
        cache_key = f'property_{self.kwargs["pk"]}'
        property_data = cache.get(cache_key)
        
        if property_data:
            logger.info(f"Cache hit for property {self.kwargs['pk']}")
            return property_data
        
        # Cache miss, get from database
        property_obj = get_object_or_404(Property, id=self.kwargs['pk'])
        cache.set(cache_key, property_obj, 60 * 60)  # Cache for 1 hour
        logger.info(f"Cache miss for property {self.kwargs['pk']}")
        
        return property_obj

# Cache statistics view
class CacheStatsView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Get Redis cache statistics"""
        metrics = get_redis_cache_metrics()
        return JsonResponse(metrics)

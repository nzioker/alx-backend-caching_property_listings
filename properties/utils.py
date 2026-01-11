import logging
from django.core.cache import cache
from django.core.cache.backends.redis import RedisCache
from django_redis import get_redis_connection
from .models import Property
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def get_all_properties(force_refresh=False):
    """
    Get all properties with Redis caching
    
    Args:
        force_refresh (bool): Force cache refresh
    
    Returns:
        QuerySet: All properties
    """
    cache_key = 'all_properties'
    
    # Check if we should force refresh
    if force_refresh:
        logger.info("Forcing cache refresh for all properties")
        cache.delete(cache_key)
    
    # Try to get from cache
    cached_data = cache.get(cache_key)
    
    if cached_data is not None and not force_refresh:
        logger.info(f"Cache hit for {cache_key}")
        return cached_data
    
    # Cache miss or force refresh
    logger.info(f"Cache miss for {cache_key}, fetching from database")
    
    # Get from database
    queryset = Property.objects.all().select_related().order_by('-created_at')
    
    # Cache for 1 hour (3600 seconds)
    cache.set(cache_key, queryset, 3600)
    
    # Also store timestamp
    cache.set(f'{cache_key}_timestamp', datetime.now().isoformat(), 3600)
    
    logger.info(f"Cached {queryset.count()} properties for 1 hour")
    
    return queryset

def get_property_by_id(property_id):
    """
    Get property by ID with caching
    
    Args:
        property_id (str/UUID): Property ID
    
    Returns:
        Property: Property instance or None
    """
    cache_key = f'property_{property_id}'
    
    # Try cache first
    cached_property = cache.get(cache_key)
    
    if cached_property:
        logger.info(f"Cache hit for property {property_id}")
        return cached_property
    
    # Cache miss, get from database
    try:
        property_obj = Property.objects.get(id=property_id)
        
        # Cache for 2 hours
        cache.set(cache_key, property_obj, 7200)
        logger.info(f"Cache miss for property {property_id}, now cached")
        
        return property_obj
    except Property.DoesNotExist:
        logger.warning(f"Property {property_id} not found")
        return None

def cache_property_queryset(queryset, cache_key, timeout=3600):
    """
    Cache a property queryset
    
    Args:
        queryset: Django queryset
        cache_key (str): Cache key
        timeout (int): Cache timeout in seconds
    """
    cache.set(cache_key, queryset, timeout)
    cache.set(f'{cache_key}_timestamp', datetime.now().isoformat(), timeout)
    logger.info(f"Cached {queryset.count()} properties under {cache_key} for {timeout} seconds")

def get_cached_properties_by_type(property_type, force_refresh=False):
    """
    Get properties by type with caching
    
    Args:
        property_type (str): Property type
        force_refresh (bool): Force cache refresh
    
    Returns:
        QuerySet: Filtered properties
    """
    cache_key = f'properties_type_{property_type}'
    
    if force_refresh:
        cache.delete(cache_key)
    
    cached_data = cache.get(cache_key)
    
    if cached_data is not None and not force_refresh:
        logger.info(f"Cache hit for properties type {property_type}")
        return cached_data
    
    # Get from database
    queryset = Property.objects.filter(
        property_type=property_type,
        is_available=True
    ).order_by('-created_at')
    
    # Cache for 30 minutes
    cache.set(cache_key, queryset, 1800)
    logger.info(f"Cached {queryset.count()} {property_type} properties")
    
    return queryset

def invalidate_property_cache(property_id=None):
    """
    Invalidate property cache
    
    Args:
        property_id (str/UUID, optional): Specific property ID
    
    Returns:
        int: Number of cache keys invalidated
    """
    if property_id:
        # Invalidate specific property cache
        cache_keys = [
            f'property_{property_id}',
            'all_properties',  # Also invalidate all properties cache
        ]
    else:
        # Invalidate all property-related caches
        cache_keys = [
            'all_properties',
            'all_properties_timestamp',
        ]
        
        # Get all property type cache keys
        for prop_type, _ in Property.PROPERTY_TYPES:
            cache_keys.append(f'properties_type_{prop_type}')
    
    # Delete cache keys
    deleted_count = 0
    for key in cache_keys:
        if cache.delete(key):
            deleted_count += 1
            logger.info(f"Invalidated cache key: {key}")
    
    logger.info(f"Invalidated {deleted_count} cache keys")
    return deleted_count

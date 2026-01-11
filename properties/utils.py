import logging
from django.core.cache import cache
from django.core.cache.backends.redis import RedisCache
from django_redis import get_redis_connection
from .models import Property
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def get_all_properties():
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

"""
Utilities for property caching and Redis metrics
"""
import logging
from django.core.cache import cache
from django_redis import get_redis_connection
from .models import Property
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# ==================== TASK 4: CACHE METRICS ANALYSIS ====================

def get_redis_cache_metrics():
    """
    Retrieve and analyze Redis cache hit/miss metrics.
    
    Returns:
        dict: Cache metrics including hit ratio
    """
    try:
        # Connect to Redis via django_redis
        redis_conn = get_redis_connection("default")
        
        # Get Redis INFO command output
        info = redis_conn.info()
        
        # Retrieve keyspace_hits and keyspace_misses
        keyspace_hits = info.get('keyspace_hits', 0)
        keyspace_misses = info.get('keyspace_misses', 0)
        
        # Calculate total requests
        total_requests = keyspace_hits + keyspace_misses
        
        # Calculate hit ratio - EXACTLY as required
        if total_requests > 0:
            hit_ratio = (keyspace_hits / total_requests) * 100
        else:
            hit_ratio = 0
        
        # Also get memory usage for comprehensive metrics
        used_memory = info.get('used_memory', 0)
        used_memory_human = info.get('used_memory_human', '0B')
        max_memory = info.get('maxmemory', 0)
        
        # Calculate memory usage percentage if max_memory is set
        memory_usage_percent = 0
        if max_memory > 0:
            memory_usage_percent = (used_memory / max_memory) * 100
        
        # Build metrics dictionary
        metrics = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'keyspace_hits': keyspace_hits,
            'keyspace_misses': keyspace_misses,
            'total_requests': total_requests,
            'hit_ratio': round(hit_ratio, 2),  # Rounded to 2 decimal places
            'memory_usage': {
                'used_memory_bytes': used_memory,
                'used_memory_human': used_memory_human,
                'max_memory_bytes': max_memory,
                'memory_usage_percent': round(memory_usage_percent, 2),
            },
            'additional_info': {
                'connected_clients': info.get('connected_clients', 0),
                'uptime_days': info.get('uptime_in_days', 0),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
            }
        }
        
        # Log the metrics
        logger.info(
            f"Cache Metrics - Hits: {keyspace_hits}, Misses: {keyspace_misses}, "
            f"Hit Ratio: {hit_ratio:.2f}%"
        )
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error retrieving Redis cache metrics: {e}")
        
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'keyspace_hits': 0,
            'keyspace_misses': 0,
            'total_requests': 0,
            'hit_ratio': 0,
        }


# ==================== EXISTING FUNCTIONS (KEEP THESE) ====================

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


# ==================== ADDITIONAL METRICS FUNCTIONS ====================

def log_cache_metrics():
    """
    Log cache metrics to /tmp/crm_report_log.txt
    """
    try:
        metrics = get_redis_cache_metrics()
        
        if metrics['status'] == 'success':
            log_entry = {
                'timestamp': metrics['timestamp'],
                'hits': metrics['keyspace_hits'],
                'misses': metrics['keyspace_misses'],
                'hit_ratio': metrics['hit_ratio'],
                'total_requests': metrics['total_requests'],
            }
            
            log_file = '/tmp/crm_report_log.txt'
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            logger.info(f"Logged cache metrics to {log_file}")
            return True
        else:
            logger.error(f"Failed to get metrics for logging: {metrics.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error logging cache metrics: {e}")
        return False


def get_cache_performance_summary():
    """
    Get a summary of cache performance
    """
    metrics = get_redis_cache_metrics()
    
    if metrics['status'] == 'success':
        summary = {
            'hit_ratio': metrics['hit_ratio'],
            'hits': metrics['keyspace_hits'],
            'misses': metrics['keyspace_misses'],
            'efficiency': 'High' if metrics['hit_ratio'] > 80 else 'Medium' if metrics['hit_ratio'] > 50 else 'Low',
            'memory_usage': metrics['memory_usage']['used_memory_human'],
            'recommendations': []
        }
        
        # Add recommendations based on hit ratio
        if metrics['hit_ratio'] < 50:
            summary['recommendations'].append("Consider increasing cache TTL for frequently accessed properties")
            summary['recommendations'].append("Implement cache warming for popular property searches")
        elif metrics['hit_ratio'] < 70:
            summary['recommendations'].append("Monitor cache patterns and adjust TTL as needed")
        
        return summary
    
    return {'error': metrics.get('error', 'Unknown error')}





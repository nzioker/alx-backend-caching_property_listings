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
from django.core.cache.backends.redis import RedisCache
from django_redis import get_redis_connection
from .models import Property
import json
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

# Add these functions to properties/utils.py (keeping existing functions)

def get_redis_cache_metrics(connection_alias='default'):
    """
    Retrieve and analyze Redis cache hit/miss metrics.
    
    Returns:
        dict: Cache metrics including hit ratio, memory usage, etc.
    """
    try:
        # Connect to Redis
        redis_conn = get_redis_connection(connection_alias)
        
        # Get Redis INFO command output
        info = redis_conn.info()
        
        # Calculate hit ratio from stats
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total_operations = hits + misses
        
        hit_ratio = 0
        if total_operations > 0:
            hit_ratio = (hits / total_operations) * 100
        
        # Memory usage
        used_memory = info.get('used_memory', 0)
        used_memory_human = info.get('used_memory_human', '0B')
        maxmemory = info.get('maxmemory', 0)
        
        memory_usage_percent = 0
        if maxmemory > 0:
            memory_usage_percent = (used_memory / maxmemory) * 100
        
        # Get cache key patterns for analysis
        cache_stats = {}
        try:
            # Scan for property-related cache keys
            property_pattern = '*property*'
            all_keys = []
            cursor = '0'
            
            # Use SCAN to avoid blocking Redis
            while cursor != 0:
                cursor, keys = redis_conn.scan(
                    cursor=cursor if cursor != '0' else 0,
                    match=property_pattern,
                    count=100
                )
                all_keys.extend(keys)
            
            # Count by key type
            cache_stats = {
                'total_keys_scanned': len(all_keys),
                'property_keys': len([k for k in all_keys if b'property' in k]),
                'keys_with_ttl': 0,
                'keys_without_ttl': 0,
            }
            
            # Sample TTL analysis (first 50 keys)
            for key in all_keys[:50]:
                try:
                    ttl = redis_conn.ttl(key)
                    if ttl == -1:
                        cache_stats['keys_without_ttl'] += 1
                    elif ttl == -2:
                        continue  # Key doesn't exist
                    else:
                        cache_stats['keys_with_ttl'] += 1
                except:
                    pass
                    
        except Exception as scan_error:
            logger.warning(f"Could not scan cache keys: {scan_error}")
            cache_stats = {'error': 'Key scan failed'}
        
        # Build comprehensive metrics dictionary
        metrics = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'connection_alias': connection_alias,
            
            # Hit/Miss Statistics
            'hit_miss_stats': {
                'hits': hits,
                'misses': misses,
                'total_operations': total_operations,
                'hit_ratio_percent': round(hit_ratio, 2),
                'miss_ratio_percent': round(100 - hit_ratio, 2) if total_operations > 0 else 0,
            },
            
            # Memory Statistics
            'memory_stats': {
                'used_memory_bytes': used_memory,
                'used_memory_human': used_memory_human,
                'max_memory_bytes': maxmemory,
                'max_memory_human': info.get('maxmemory_human', '0B'),
                'memory_usage_percent': round(memory_usage_percent, 2),
                'peak_memory_bytes': info.get('used_memory_peak', 0),
                'peak_memory_human': info.get('used_memory_peak_human', '0B'),
                'fragmentation_ratio': round(info.get('mem_fragmentation_ratio', 0), 2),
            },
            
            # Cache Statistics
            'cache_stats': cache_stats,
            
            # Connection Statistics
            'connection_stats': {
                'connected_clients': info.get('connected_clients', 0),
                'blocked_clients': info.get('blocked_clients', 0),
                'max_clients': info.get('maxclients', 0),
                'client_utilization_percent': round(
                    info.get('connected_clients', 0) / max(1, info.get('maxclients', 1)) * 100, 
                    2
                ),
            },
            
            # Performance Metrics
            'performance_stats': {
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'uptime_days': info.get('uptime_in_days', 0),
                'uptime_seconds': info.get('uptime_in_seconds', 0),
                'rejected_connections': info.get('rejected_connections', 0),
            },
            
            # Eviction & Expiration
            'eviction_stats': {
                'eviction_policy': info.get('maxmemory_policy', 'noeviction'),
                'evicted_keys': info.get('evicted_keys', 0),
                'expired_keys': info.get('expired_keys', 0),
                'keyspace_hits': hits,
                'keyspace_misses': misses,
            },
            
            # Persistence (if configured)
            'persistence_stats': {
                'rdb_last_save_time': info.get('rdb_last_save_time', 0),
                'rdb_changes_since_last_save': info.get('rdb_changes_since_last_save', 0),
                'aof_enabled': info.get('aof_enabled', 0) == 1,
                'aof_rewrite_in_progress': info.get('aof_rewrite_in_progress', 0) == 1,
            },
        }
        
        # Log the metrics
        logger.info(
            f"Cache Metrics - Hits: {hits}, Misses: {misses}, "
            f"Hit Ratio: {hit_ratio:.2f}%, Memory: {used_memory_human}"
        )
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error retrieving Redis cache metrics: {e}")
        
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }


def analyze_cache_patterns(connection_alias='default'):
    """
    Analyze cache access patterns and provide optimization recommendations.
    
    Returns:
        dict: Analysis results and recommendations
    """
    try:
        redis_conn = get_redis_connection(connection_alias)
        
        # Get recent metrics
        metrics = get_redis_cache_metrics(connection_alias)
        
        if metrics['status'] == 'error':
            return metrics
        
        analysis = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'analysis': {},
            'recommendations': [],
        }
        
        hit_stats = metrics['hit_miss_stats']
        mem_stats = metrics['memory_stats']
        perf_stats = metrics['performance_stats']
        
        # Analyze hit ratio
        hit_ratio = hit_stats['hit_ratio_percent']
        if hit_ratio < 50:
            analysis['analysis']['hit_ratio_status'] = 'POOR'
            analysis['recommendations'].append(
                f"Hit ratio is low ({hit_ratio}%). Consider increasing cache TTLs "
                f"or caching more frequently accessed data."
            )
        elif hit_ratio < 80:
            analysis['analysis']['hit_ratio_status'] = 'FAIR'
            analysis['recommendations'].append(
                f"Hit ratio is acceptable ({hit_ratio}%). Monitor for improvements."
            )
        else:
            analysis['analysis']['hit_ratio_status'] = 'EXCELLENT'
            analysis['recommendations'].append(
                f"Hit ratio is excellent ({hit_ratio}%). Cache is well utilized."
            )
        
        # Analyze memory usage
        memory_usage = mem_stats['memory_usage_percent']
        if memory_usage > 90:
            analysis['analysis']['memory_status'] = 'CRITICAL'
            analysis['recommendations'].append(
                f"Memory usage is critical ({memory_usage}%). Consider increasing maxmemory "
                f"or optimizing cache eviction policy."
            )
        elif memory_usage > 70:
            analysis['analysis']['memory_status'] = 'HIGH'
            analysis['recommendations'].append(
                f"Memory usage is high ({memory_usage}%). Monitor closely."
            )
        else:
            analysis['analysis']['memory_status'] = 'HEALTHY'
        
        # Analyze fragmentation
        fragmentation = mem_stats['fragmentation_ratio']
        if fragmentation > 1.5:
            analysis['analysis']['fragmentation_status'] = 'HIGH'
            analysis['recommendations'].append(
                f"Memory fragmentation is high ({fragmentation}). "
                f"Consider restarting Redis or adjusting memory allocation."
            )
        
        # Analyze connection utilization
        conn_util = metrics['connection_stats']['client_utilization_percent']
        if conn_util > 80:
            analysis['analysis']['connection_status'] = 'HIGH_LOAD'
            analysis['recommendations'].append(
                f"Connection utilization is high ({conn_util}%). "
                f"Consider increasing maxclients or connection pooling."
            )
        
        # Add summary
        analysis['summary'] = {
            'hit_ratio': hit_ratio,
            'memory_usage_percent': memory_usage,
            'total_operations': hit_stats['total_operations'],
            'cache_efficiency': 'Efficient' if hit_ratio > 70 else 'Needs Improvement',
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing cache patterns: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }


def get_cache_health_check(connection_alias='default'):
    """
    Perform a comprehensive cache health check.
    
    Returns:
        dict: Health check results with status indicators
    """
    try:
        redis_conn = get_redis_connection(connection_alias)
        
        # Test basic connectivity
        start_time = time.time()
        redis_conn.ping()
        ping_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Get metrics
        metrics = get_redis_cache_metrics(connection_alias)
        
        health_check = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'connectivity': {
                'ping_response_ms': round(ping_time, 2),
                'status': 'HEALTHY' if ping_time < 10 else 'SLOW',
                'message': 'Redis is reachable' if ping_time < 100 else 'Redis response is slow',
            },
            'components': {},
        }
        
        if metrics['status'] == 'success':
            # Check hit ratio health
            hit_ratio = metrics['hit_miss_stats']['hit_ratio_percent']
            health_check['components']['hit_ratio'] = {
                'value': hit_ratio,
                'status': 'HEALTHY' if hit_ratio > 70 else 'WARNING' if hit_ratio > 40 else 'CRITICAL',
                'threshold': 70,
            }
            
            # Check memory health
            mem_usage = metrics['memory_stats']['memory_usage_percent']
            health_check['components']['memory_usage'] = {
                'value': mem_usage,
                'status': 'HEALTHY' if mem_usage < 80 else 'WARNING' if mem_usage < 90 else 'CRITICAL',
                'threshold': 80,
            }
            
            # Check connection health
            connections = metrics['connection_stats']['connected_clients']
            max_clients = metrics['connection_stats']['max_clients']
            conn_percent = (connections / max(1, max_clients)) * 100
            health_check['components']['connections'] = {
                'value': connections,
                'max': max_clients,
                'utilization_percent': round(conn_percent, 2),
                'status': 'HEALTHY' if conn_percent < 80 else 'WARNING' if conn_percent < 90 else 'CRITICAL',
            }
            
            # Overall health status
            critical_count = sum(1 for comp in health_check['components'].values() 
                               if comp['status'] == 'CRITICAL')
            warning_count = sum(1 for comp in health_check['components'].values() 
                              if comp['status'] == 'WARNING')
            
            if critical_count > 0:
                health_check['overall_status'] = 'CRITICAL'
            elif warning_count > 0:
                health_check['overall_status'] = 'WARNING'
            else:
                health_check['overall_status'] = 'HEALTHY'
                
        else:
            health_check['overall_status'] = 'ERROR'
            health_check['error'] = metrics.get('error', 'Unknown error')
        
        return health_check
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'UNREACHABLE',
        }


def log_cache_metrics_to_file(filename='/tmp/redis_cache_metrics.log'):
    """
    Log cache metrics to a file for historical analysis.
    
    Args:
        filename (str): Path to log file
    """
    try:
        metrics = get_redis_cache_metrics()
        
        if metrics['status'] == 'success':
            log_entry = {
                'timestamp': metrics['timestamp'],
                'hit_ratio': metrics['hit_miss_stats']['hit_ratio_percent'],
                'memory_usage': metrics['memory_stats']['memory_usage_percent'],
                'total_operations': metrics['hit_miss_stats']['total_operations'],
                'connected_clients': metrics['connection_stats']['connected_clients'],
            }
            
            with open(filename, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            logger.info(f"Logged cache metrics to {filename}")
            return True
        else:
            logger.error(f"Failed to get metrics for logging: {metrics.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error logging cache metrics: {e}")
        return False


def get_cache_performance_report(days=7):
    """
    Generate a cache performance report over a period.
    
    Args:
        days (int): Number of days to analyze
        
    Returns:
        dict: Performance report with trends
    """
    try:
        # Get current metrics
        current_metrics = get_redis_cache_metrics()
        
        if current_metrics['status'] != 'success':
            return current_metrics
        
        # Simulate historical data (in production, you'd query from logs/database)
        report = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'period_days': days,
            'current_metrics': current_metrics,
            'historical_trends': {
                'hit_ratio_trend': 'stable',  # Would be calculated from historical data
                'memory_trend': 'stable',
                'load_trend': 'stable',
            },
            'performance_summary': {
                'average_hit_ratio': current_metrics['hit_miss_stats']['hit_ratio_percent'],
                'peak_memory_usage': current_metrics['memory_stats']['peak_memory_bytes'],
                'total_operations': current_metrics['performance_stats']['total_commands_processed'],
            },
        }
        
        # Generate recommendations based on trends
        recommendations = []
        
        hit_ratio = current_metrics['hit_miss_stats']['hit_ratio_percent']
        if hit_ratio < 60:
            recommendations.append(
                "Consider implementing cache warming for frequently accessed properties."
            )
            recommendations.append(
                "Review cache TTLs - shorter TTLs for dynamic data, longer for static data."
            )
        
        mem_usage = current_metrics['memory_stats']['memory_usage_percent']
        if mem_usage > 75:
            recommendations.append(
                "Monitor memory usage closely. Consider increasing Redis maxmemory if needed."
            )
            recommendations.append(
                "Review cache eviction policy. 'allkeys-lru' is recommended for property listings."
            )
        
        if recommendations:
            report['recommendations'] = recommendations
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating performance report: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }


def clear_cache_and_get_metrics(connection_alias='default'):
    """
    Clear cache and get fresh metrics (for testing/reset scenarios).
    
    Returns:
        dict: Metrics after cache clear
    """
    try:
        logger.info("Clearing cache and collecting fresh metrics...")
        
        # Clear all property-related caches
        invalidated = invalidate_property_cache()
        
        # Get fresh metrics
        metrics = get_redis_cache_metrics(connection_alias)
        
        if metrics['status'] == 'success':
            metrics['cache_clear'] = {
                'keys_invalidated': invalidated,
                'timestamp': datetime.now().isoformat(),
                'message': f'Invalidated {invalidated} cache keys',
            }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error clearing cache and getting metrics: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }

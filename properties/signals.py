import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Property

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Property)
def invalidate_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalidate cache when a property is saved
    """
    cache_keys_to_delete = [
        'all_properties',
        'all_properties_timestamp',
        f'properties_type_{instance.property_type}',
    ]
    
    # Add featured properties cache key if property is featured
    if instance.featured:
        cache_keys_to_delete.append('featured_properties')
    
    # Delete cache keys
    deleted_count = 0
    for key in cache_keys_to_delete:
        if cache.delete(key):
            deleted_count += 1
    
    logger.info(
        f"Cache invalidated on {'creation' if created else 'update'} "
        f"of property {instance.id}. {deleted_count} cache keys deleted."
    )
    
    # Also invalidate the specific property cache
    property_cache_key = f'property_{instance.id}'
    if cache.delete(property_cache_key):
        logger.info(f"Invalidated cache for property {instance.id}")
        deleted_count += 1
    
    # Signal to update search index (if you have one)
    update_search_index(instance, created)

@receiver(post_delete, sender=Property)
def invalidate_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate cache when a property is deleted
    """
    cache_keys_to_delete = [
        'all_properties',
        'all_properties_timestamp',
        f'properties_type_{instance.property_type}',
        f'property_{instance.id}',
    ]
    
    if instance.featured:
        cache_keys_to_delete.append('featured_properties')
    
    deleted_count = 0
    for key in cache_keys_to_delete:
        if cache.delete(key):
            deleted_count += 1
    
    logger.info(
        f"Cache invalidated on deletion of property {instance.id}. "
        f"{deleted_count} cache keys deleted."
    )
    
    # Signal to remove from search index
    remove_from_search_index(instance)

@receiver(pre_save, sender=Property)
def check_property_changes(sender, instance, **kwargs):
    """
    Check what fields changed to optimize cache invalidation
    """
    if instance.pk:
        try:
            old_instance = Property.objects.get(pk=instance.pk)
            
            # Check if property type changed
            if old_instance.property_type != instance.property_type:
                logger.info(
                    f"Property type changed from {old_instance.property_type} "
                    f"to {instance.property_type}"
                )
                # Invalidate old property type cache
                cache.delete(f'properties_type_{old_instance.property_type}')
            
            # Check if featured status changed
            if old_instance.featured != instance.featured:
                logger.info(
                    f"Featured status changed from {old_instance.featured} "
                    f"to {instance.featured}"
                )
                cache.delete('featured_properties')
                
        except Property.DoesNotExist:
            pass

def update_search_index(instance, created):
    """
    Update search index (placeholder for actual search implementation)
    """
    # This would be implemented with Elasticsearch, Algolia, etc.
    logger.debug(f"Search index update needed for property {instance.id}")

def remove_from_search_index(instance):
    """
    Remove from search index (placeholder)
    """
    logger.debug(f"Remove from search index needed for property {instance.id}")

# Batch cache invalidation signal
def invalidate_all_property_caches():
    """
    Invalidate all property-related caches
    Useful for bulk operations or cache cleanup
    """
    # Pattern match to find all property cache keys
    from django_redis import get_redis_connection
    
    try:
        redis_conn = get_redis_connection("default")
        
        # Find all keys with property prefix
        pattern = "property_listings:*property*"
        keys = redis_conn.keys(pattern)
        
        if keys:
            deleted = redis_conn.delete(*keys)
            logger.info(f"Bulk cache invalidation: {deleted} keys deleted")
        else:
            logger.info("No property cache keys found for bulk invalidation")
            
    except Exception as e:
        logger.error(f"Error during bulk cache invalidation: {e}")

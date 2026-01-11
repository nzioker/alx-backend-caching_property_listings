from django.apps import AppConfig

class PropertiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'properties'
    
    def ready(self):
        """
        Import signals when app is ready
        """
        import properties.signals
        
        # Initialize cache on startup
        self.initialize_cache()
    
    def initialize_cache(self):
        """
        Initialize cache with default values if needed
        """
        from django.core.cache import cache
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Check if cache is working
        try:
            cache.set('cache_test', 'working', 10)
            test_result = cache.get('cache_test')
            
            if test_result == 'working':
                logger.info("Cache initialization successful")
            else:
                logger.warning("Cache test failed - unexpected result")
                
        except Exception as e:
            logger.error(f"Cache initialization failed: {e}")

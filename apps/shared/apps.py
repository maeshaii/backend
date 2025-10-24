from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SharedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shared'
    scheduler = None  # Store scheduler instance to prevent garbage collection
    
    def ready(self):
        """
        Called when Django starts
        Initialize the scheduler here
        """
        import os
        
        # Prevent multiple scheduler instances
        # Check if already initialized
        if hasattr(self, '_scheduler_started') and self._scheduler_started:
            logger.info("Scheduler already initialized, skipping...")
            return
            
        try:
            from .scheduler import start_scheduler
            # Store the scheduler to prevent garbage collection
            SharedConfig.scheduler = start_scheduler()
            self._scheduler_started = True
            logger.info("✅ Scheduler initialized successfully in ready()")
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)

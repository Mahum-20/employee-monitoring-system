from django.core.management.base import BaseCommand
from monitoring_app.services import cleanup_expired_recordings, get_storage_usage

class Command(BaseCommand):
    help = 'Automatically delete employee screen recordings older than 24 hours to enforce 400MB storage limit'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting 24-hour recording cleanup operation..."))
        
        result = cleanup_expired_recordings()
        storage = get_storage_usage()
        
        self.stdout.write(self.style.SUCCESS(
            f"Cleanup complete! Removed {result['recordings_deleted']} expired recordings and {result['orphans_cleaned']} orphaned files. "
            f"Freed {result['freed_mb']} MB of space."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Current Storage: {storage['used_mb']} MB / {storage['limit_mb']} MB ({storage['used_percent']}% used)"
        ))

import os
import time
from django.conf import settings
from django.utils import timezone
from .models import ScreenRecording

def get_storage_usage():
    """
    Returns server storage stats against the 400 MB cap.
    """
    limit_mb = getattr(settings, 'SERVER_STORAGE_LIMIT_MB', 400)
    media_root = settings.MEDIA_ROOT
    
    total_bytes = 0
    if os.path.exists(media_root):
        for root, _, files in os.walk(media_root):
            for file in files:
                file_path = os.path.path = os.path.join(root, file)
                try:
                    total_bytes += os.path.getsize(file_path)
                except OSError:
                    pass
    
    used_mb = round(total_bytes / (1024 * 1024), 2)
    free_mb = max(0.0, round(limit_mb - used_mb, 2))
    used_percent = min(100.0, round((used_mb / limit_mb) * 100, 1)) if limit_mb > 0 else 0.0
    
    # Status color indicator
    if used_percent >= 90:
        status_level = 'danger' # Red warning
    elif used_percent >= 70:
        status_level = 'warning' # Yellow warning
    else:
        status_level = 'success' # Green healthy

    return {
        'limit_mb': limit_mb,
        'used_mb': used_mb,
        'free_mb': free_mb,
        'used_bytes': total_bytes,
        'used_percent': used_percent,
        'status_level': status_level,
    }


def cleanup_expired_recordings():
    """
    Deletes all ScreenRecording entries and video files that are older than 24 hours.
    """
    now = timezone.now()
    expired_recordings = ScreenRecording.objects.filter(expires_at__lte=now)
    count = expired_recordings.count()
    
    bytes_freed = 0
    for rec in expired_recordings:
        bytes_freed += rec.file_size_bytes
        rec.delete() # Deletes file from storage and DB row
        
    freed_mb = round(bytes_freed / (1024 * 1024), 2)

    # Sweep media root for orphaned recording files older than 24 hours
    media_root = settings.MEDIA_ROOT
    orphans_cleaned = 0
    if os.path.exists(media_root):
        current_time = time.time()
        for root, _, files in os.walk(media_root):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # 24 hours = 86400 seconds
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > 86400:
                        os.remove(file_path)
                        orphans_cleaned += 1
                except OSError:
                    pass

    return {
        'recordings_deleted': count,
        'freed_mb': freed_mb,
        'orphans_cleaned': orphans_cleaned,
        'timestamp': now,
    }

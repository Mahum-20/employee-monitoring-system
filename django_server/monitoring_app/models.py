import os
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.conf import settings

class Employee(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    employee_code = models.CharField(max_length=50, unique=True, help_text="Unique Identifier for Employee Laptop Agent")
    department = models.CharField(max_length=100, default="General")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.employee_code})"

    @property
    def total_recordings_count(self):
        return self.recordings.count()

    @property
    def total_storage_mb(self):
        bytes_sum = sum(r.file_size_bytes for r in self.recordings.all())
        return round(bytes_sum / (1024 * 1024), 2)

    @property
    def is_online(self):
        latest_device = self.devices.order_by('-last_ping').first()
        if latest_device and latest_device.last_ping:
            return (timezone.now() - latest_device.last_ping) < timedelta(minutes=5)
        return False


class Device(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='devices')
    hostname = models.CharField(max_length=200)
    os_info = models.CharField(max_length=200, blank=True, default='')
    mac_address = models.CharField(max_length=100, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_ping = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.hostname} - {self.employee.name}"


class ScreenRecording(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='recordings')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='recordings')
    video_file = models.FileField(upload_to='recordings/%Y/%m/%d/')
    recorded_at = models.DateTimeField(default=timezone.now)
    duration_seconds = models.IntegerField(default=0, help_text="Duration in seconds")
    file_size_bytes = models.BigIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-recorded_at']

    def save(self, *args, **kwargs):
        if not self.expires_at and self.recorded_at:
            self.expires_at = self.recorded_at + timedelta(hours=24)
        if self.video_file and hasattr(self.video_file, 'size') and not self.file_size_bytes:
            self.file_size_bytes = self.video_file.size
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def time_until_expiration(self):
        remaining = self.expires_at - timezone.now()
        if remaining.total_seconds() <= 0:
            return "Expired (Pending Cleanup)"
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m"

    @property
    def formatted_duration(self):
        if self.duration_seconds >= 3600:
            h = self.duration_seconds // 3600
            m = (self.duration_seconds % 3600) // 60
            return f"{h}h {m}m"
        elif self.duration_seconds >= 60:
            m = self.duration_seconds // 60
            s = self.duration_seconds % 60
            return f"{m}m {s}s"
        return f"{self.duration_seconds}s"

    @property
    def file_size_mb(self):
        return round(self.file_size_bytes / (1024 * 1024), 2)

    def delete(self, *args, **kwargs):
        # Delete file from storage when model instance is deleted
        if self.video_file:
            if os.path.isfile(self.video_file.path):
                try:
                    os.remove(self.video_file.path)
                except OSError:
                    pass
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Recording: {self.employee.name} at {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"

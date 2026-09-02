import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_monitoring.settings')
django.setup()

from django.utils import timezone
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from monitoring_app.models import Employee, Device, ScreenRecording
from monitoring_app.services import cleanup_expired_recordings, get_storage_usage

# Create default Employer Admin User if not exists
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@company.local', 'admin')
    print("[+] Created Employer Admin Account (Username: admin | Password: admin)")

print("Seeding test employee and recording data...")

# 1. Create Employees
emp1, _ = Employee.objects.get_or_create(
    employee_code="EMP001",
    defaults={
        "name": "Sarah Connor",
        "email": "sarah@cyberdyne.local",
        "department": "Engineering"
    }
)

emp2, _ = Employee.objects.get_or_create(
    employee_code="EMP002",
    defaults={
        "name": "Alex Mercer",
        "email": "alex@company.local",
        "department": "Sales & Support"
    }
)

# 2. Create Device
dev1, _ = Device.objects.get_or_create(
    employee=emp1,
    hostname="SARAH-LAPTOP-WIN11",
    defaults={
        "os_info": "Windows 11 Pro",
        "mac_address": "00:11:22:33:44:55",
        "ip_address": "192.168.1.105"
    }
)

# 3. Generate a tiny dummy sample video file for demonstration
dummy_video_bytes = b"HEADER_WEBM_SIMULATION_DATA_CHUNK_" * 1024 * 10 # ~34 KB test chunk

# Active recording (recorded 2 hours ago -> expires in 22 hours)
rec_active = ScreenRecording(
    employee=emp1,
    device=dev1,
    recorded_at=timezone.now() - timedelta(hours=2),
    duration_seconds=300,
)
rec_active.video_file.save("demo_active.webm", ContentFile(dummy_video_bytes), save=True)

# Expired recording (recorded 26 hours ago -> expired 2 hours ago)
rec_expired = ScreenRecording(
    employee=emp2,
    recorded_at=timezone.now() - timedelta(hours=26),
    duration_seconds=300,
)
rec_expired.video_file.save("demo_expired.webm", ContentFile(dummy_video_bytes), save=True)

print(f"[+] Created Employees: {emp1}, {emp2}")
print(f"[+] Created Active Recording: {rec_active} (Expires in: {rec_active.time_until_expiration})")
print(f"[+] Created Expired Recording: {rec_expired} (Expired: {rec_expired.is_expired})")

# Check Storage
storage = get_storage_usage()
print(f"[+] Server Storage: {storage['used_mb']} MB / {storage['limit_mb']} MB ({storage['used_percent']}% used)")

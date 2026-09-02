import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_monitoring.settings')
django.setup()

from django.contrib.auth.models import User
from monitoring_app.models import Employee, Device, ScreenRecording

print("=== INITIALIZING FRESH REAL-TIME DATABASE ===")

# Clear all demo data
ScreenRecording.objects.all().delete()
Device.objects.all().delete()
Employee.objects.all().delete()

print("[+] Cleared all placeholder and mock employee records.")

# Create Superuser Admin
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@company.local', 'admin')
    print("[+] Created Employer Admin Account: admin / admin")
else:
    print("[+] Admin Account exists: admin / admin")

print("[+] Database ready! Dashboard will now populate ONLY when real employee laptops send data.\n")

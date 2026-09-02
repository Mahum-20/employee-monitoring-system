import os
import subprocess

print("=== Building Standalone Employee Monitor Executable ===")

pyinstaller_cmd = [
    "pyinstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "EmployeeMonitorClient",
    "--add-data", "config.json;.",
    "main_gui.py"
]

print(f"Running command: {' '.join(pyinstaller_cmd)}")
try:
    res = subprocess.run(pyinstaller_cmd, check=True)
    print("\n[+] Build successful! Standalone software folder created in: dist/EmployeeMonitorClient/")
except Exception as e:
    print(f"[-] Build error (PyInstaller may need to be installed): {e}")

import os
import sys
import shutil
import subprocess

print("=================================================================")
print("          BUILDING ABCBUILD AGENT INSTALLER (.EXE)              ")
print("=================================================================")

script_dir = os.path.dirname(os.path.abspath(__file__))
dist_dir = os.path.join(script_dir, "dist")
build_dir = os.path.join(script_dir, "build")

# 1. Run PyInstaller to compile silent_agent.py as abcbuild.exe
pyinstaller_cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--noconsole",
    "--name", "abcbuild",
    "silent_agent.py"
]

print("[*] Compiling abcbuild.exe binary...")
try:
    subprocess.run(pyinstaller_cmd, check=True, cwd=script_dir)
    print("[+] Compilation complete!")
except Exception as e:
    print(f"[-] PyInstaller compilation failed: {e}")
    sys.exit(1)

# 2. Create standard installer package folder
installer_package_dir = os.path.join(dist_dir, "ABCBuild_Installer_Package")
os.makedirs(installer_package_dir, exist_ok=True)

compiled_exe = os.path.join(dist_dir, "abcbuild.exe")
target_exe = os.path.join(installer_package_dir, "abcbuild.exe")
shutil.copy2(compiled_exe, target_exe)

config_src = os.path.join(script_dir, "config.json")
if os.path.exists(config_src):
    shutil.copy2(config_src, os.path.join(installer_package_dir, "config.json"))

# 3. Create Windows Silent Auto-Installer Script (Install.bat)
installer_bat_content = """@echo off
:: ABCBuild Silent Installer
title Installing ABCBuild...

set "TARGET_DIR=%APPDATA%\\ABCBuildAgent"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo Installing ABCBuild silently...
copy /Y "%~dp0abcbuild.exe" "%TARGET_DIR%\\abcbuild.exe" >nul
if exist "%~dp0config.json" copy /Y "%~dp0config.json" "%TARGET_DIR%\\config.json" >nul

:: Register in Windows Auto-Start Registry Key (Runs on Windows Boot)
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "ABCBuildAgent" /t REG_SZ /d "\"%TARGET_DIR%\\abcbuild.exe\"" /f >nul

:: Launch the background agent immediately
start "" "%TARGET_DIR%\\abcbuild.exe"

echo Installation Complete!
"""

install_bat_path = os.path.join(installer_package_dir, "Install_ABCBuild_Service.bat")
with open(install_bat_path, "w") as f:
    f.write(installer_bat_content)

print(f"\n=================================================================")
print(f"  [SUCCESS] ABCBUILD INSTALLER PACKAGE CREATED SUCCESSFULLY!")
print(f"  Folder Location: {installer_package_dir}")
print(f"  Files inside:")
print(f"    1. abcbuild.exe                 (Windowless agent binary)")
print(f"    2. config.json                  (Server URL & employee settings)")
print(f"    3. Install_ABCBuild_Service.bat (One-click silent installer)")
print(f"=================================================================\n")

@echo off
title USBGuard Service Installer
echo ===================================================
echo   USB Port Monitor : The Forensic Tool
echo   Background Service Installer
echo ===================================================
echo.

:: Admin check (Agar admin nahi hai toh error dega)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run this installer as Administrator!
    pause
    exit /b
)

echo [1/3] Installing the Background Service...
python usbguard_service.py install

echo.
echo [2/3] Starting the Service...
python usbguard_service.py start

echo.
echo [3/3] Setting Service to Auto-Start on PC Boot...
sc config USBGuardForensics start= auto

echo.
echo ===================================================
echo ✅ SUCCESS! 
echo The service is now installed and running in the background.
echo You can close this window. Even if you close the GUI, 
echo the background service will keep monitoring USB ports.
echo ===================================================
pause
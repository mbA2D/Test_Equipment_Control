# Packaging and Installation Guide: Battery Tester App

This document outlines the process for converting the Python source code into a professional Windows Installer.

## Phase 0: Run from Source (Development)

From the project root, run the Qt battery application directly with the local
virtual environment:

```powershell
.\.venv\Scripts\python.exe battery_test.py
```

This is the development workflow for testing source-code changes before
building the standalone executable.

## Phase 1: Create the Application Executable (PyInstaller)
Before creating an installer, the Python code must be bundled into a standalone `.exe`.

The PyInstaller specification includes the DAQ configuration CSV files under
`lab_equipment`, so DAQ setup remains available in the packaged application.

**Command:**
```powershell
# Use the project environment

# Bundle into a single file without a console window
.\.venv\Scripts\python.exe -m PyInstaller installer\battery_test.spec
```
**Result:** The application is created at `dist\battery_test.exe`.

The spec file builds the Qt battery application only. One-off hardware scripts
are not included in this executable and may use their separately maintained UI
dependencies. Install those optional dependencies with
`pip install .[legacy-hardware-ui]` when using the one-off scripts.

### Build verification

After building, verify the artifact before packaging it:

```powershell
Test-Path dist\battery_test.exe
Get-Item dist\battery_test.exe | Select-Object FullName, Length, LastWriteTime
Start-Process .\dist\battery_test.exe
```

Confirm that the window opens without a console, the profile editor loads, and
the application can be closed cleanly. Hardware connection and VISA-driver
validation must still be performed on the target lab workstation.

---

## Phase 2: Create the Windows Installer (NSIS)
To provide a professional setup wizard with shortcuts and an uninstaller.

### 1. Prerequisites
- Install **NSIS (Nullsoft Scriptable Install System)** from [nsis.sourceforge.io](https://nsis.sourceforge.io/Download).

### 2. The Script
The configuration is stored in `installer\battery_test_installer.nsi`.

### 3. Compilation
**Option A (GUI):** 
Right-click `installer\battery_test_installer.nsi` $\rightarrow$ **Compile NSIS Script**.

**Option B (CLI):**
```powershell
Push-Location installer
makensis battery_test_installer.nsi
Pop-Location
```
**Result:** The final installer is created as `dist\BatteryTester_Setup.exe`.

---

## Phase 3: Deployment Checklist
When distributing the `BatteryTester_Setup.exe` to other computers, ensure the following:

1. **VISA Drivers:** The target computer **MUST** have NI-VISA or Keysight VISA installed. The installer handles the software, but not the system-level hardware drivers.
2. **Admin Rights:** The installer requires administrator privileges to write to `C:\Program Files`.

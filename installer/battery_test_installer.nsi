 ; -------------------------------------------------------------------------
; MODERN NSIS Script for Battery Tester App (MUI2)
; -------------------------------------------------------------------------

; Include Modern UI
!include "MUI2.nsh"

; Name of the installer
Name "Battery Tester App"
OutFile "..\dist\BatteryTester_Setup.exe"

; Default installation folder
InstallDir "$PROGRAMFILES\BatteryTester"

; Request admin privileges
RequestExecutionLevel admin

; --- MUI Appearance ---
!define MUI_ABORTWARNING

; --- MUI Pages ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; --- MUI Languages ---
!insertmacro MUI_LANGUAGE "English"

; --- Installation Section ---
Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    
    File "..\dist\battery_test.exe"
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    CreateShortcut "$SMPROGRAMS\Battery Tester.lnk" "$INSTDIR\battery_test.exe"
    CreateShortcut "$DESKTOP\Battery Tester.lnk" "$INSTDIR\battery_test.exe"
SectionEnd

; --- Uninstallation Section ---
Section "Uninstall"
    Delete "$INSTDIR\battery_test.exe"
    Delete "$INSTDIR\uninstall.exe"
    Delete "$SMPROGRAMS\Battery Tester.lnk"
    Delete "$DESKTOP\Battery Tester.lnk"
    RMDir "$INSTDIR"
SectionEnd

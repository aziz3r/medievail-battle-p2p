@echo off
:: ============================================================
:: compile.bat - Compile reseau.c en reseau.exe (Windows)
:: Utilise WinLibs GCC (installé via winget)
:: ============================================================

set GCC_PATH=C:\Users\jamai\AppData\Local\Microsoft\WinGet\Packages\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\mingw64\bin\gcc.exe

echo [COMPILE] Compilation de reseau.c...
"%GCC_PATH%" reseau.c -o reseau.exe -lws2_32 -Wall

if %ERRORLEVEL% EQU 0 (
    echo [OK] reseau.exe compile avec succes !
) else (
    echo [ERREUR] La compilation a echoue.
)
pause

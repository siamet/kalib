@echo off
REM Test PySide6 installation on Windows
REM Run this after installing to verify DLL issues are resolved

echo ========================================================================
echo Kalib - PySide6 Installation Test for Windows
echo ========================================================================
echo.

echo Testing Python availability...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    echo Please activate conda environment: conda activate kalib
    pause
    exit /b 1
)
echo [OK] Python found
echo.

echo Testing PySide6 import...
python -c "from PySide6.QtWidgets import QApplication; print('[OK] PySide6 QtWidgets imported successfully')"
if errorlevel 1 (
    echo.
    echo [ERROR] PySide6 import failed!
    echo.
    echo SOLUTIONS:
    echo 1. Install Visual C++ Redistributables:
    echo    https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo 2. Reinstall PySide6:
    echo    pip uninstall PySide6 -y
    echo    pip install PySide6==6.6.3.1
    echo.
    echo 3. See WINDOWS_SETUP.md for more solutions
    echo.
    pause
    exit /b 1
)
echo.

echo Testing PySide6 version...
python -c "import PySide6; print(f'[OK] PySide6 version: {PySide6.__version__}')"
echo.

echo Testing Qt library paths...
python -c "from PySide6.QtCore import QLibraryInfo; print(f'[OK] Qt prefix: {QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath)}')"
echo.

echo ========================================================================
echo SUCCESS! PySide6 is working correctly
echo ========================================================================
echo.
echo You can now launch Kalib:
echo    python -m kalib.main
echo.
pause

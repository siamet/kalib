# Windows Setup Guide for Kalib

## Common Issue: DLL Load Failed Error

**Error**: `ImportError: DLL load failed while importing QtWidgets: The specified procedure could not be found.`

This is a known issue with PySide6 on Windows. Follow the solutions below in order.

---

## Solution 1: Install Visual C++ Redistributables (Most Common Fix)

PySide6 requires Microsoft Visual C++ Redistributables. Install the latest:

### Download and Install
1. **Download**: [Microsoft Visual C++ Redistributables](https://aka.ms/vs/17/release/vc_redist.x64.exe)
2. **Run installer** as Administrator
3. **Restart** your computer after installation
4. **Try running Kalib again**

### Alternative: Install via Chocolatey
```powershell
# Run PowerShell as Administrator
choco install vcredist-all
```

---

## Solution 2: Clean Reinstall PySide6

### Step 1: Remove Existing Installation
```bash
# Activate your virtual environment
.venv\Scripts\activate

# Uninstall PySide6
pip uninstall PySide6 -y

# Clear UV cache
uv pip cache clear
```

### Step 2: Reinstall with Specific Version
Try these in order until one works:

**Option A: Stable Version (Recommended)**
```bash
uv pip install PySide6==6.8.0.2
```

**Option B: Latest Stable**
```bash
pip install PySide6==6.8.0.2
```

**Option C: LTS Version (Most Stable)**
```bash
pip install PySide6==6.6.3.1
```

### Step 3: Verify Installation
```bash
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

---

## Solution 3: Recreate Virtual Environment

If the above doesn't work, recreate the environment from scratch:

### Step 1: Remove Old Environment
```bash
# Deactivate current environment
deactivate

# Remove old environment
rmdir /s .venv
```

### Step 2: Create New Environment and Reinstall

```bash
# Create fresh virtual environment
uv venv --python 3.12

# Activate it
.venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

### Step 3: Test Import
```bash
python -c "from PySide6.QtWidgets import QApplication; print('Success!')"
```

---

## Solution 4: Check for Conflicting Qt Installations

### Check System PATH
Open PowerShell and check for multiple Qt installations:
```powershell
$env:PATH -split ';' | Select-String -Pattern 'qt|Qt'
```

**If you see multiple Qt paths**, you may have conflicts. Solutions:
1. Uninstall other Qt installations (Qt Designer, Qt Creator, etc.)
2. Or, temporarily modify PATH when running Kalib

### Temporary PATH Fix
Create a `run_kalib.bat` file:
```batch
@echo off
REM Activate virtual environment and run Kalib
call .venv\Scripts\activate.bat
python -m kalib.main
```

---

## Solution 5: Check for Antivirus Interference

Some antivirus software blocks Qt DLLs. Try:
1. **Temporarily disable antivirus**
2. **Run Kalib**
3. If it works, **add exception** to antivirus for:
   - `.venv\Lib\site-packages\PySide6\`
   - Your Kalib installation directory

---

## Solution 6: Use Specific PySide6 Version

Try a different PySide6 version known to work on Windows:

```bash
# Activate environment
.venv\Scripts\activate

# Uninstall current version
pip uninstall PySide6 -y

# Install specific tested version
uv pip install PySide6==6.6.3.1

# Verify
python -c "from PySide6.QtWidgets import QApplication; print('OK')"
```

---

## Solution 7: Use Python 3.11 Instead of 3.12

If none of the above work, try Python 3.11 (better Windows compatibility for some systems):

```bash
# Remove old environment
rmdir /s .venv

# Create new environment with Python 3.11
uv venv --python 3.11

# Activate
.venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

---

## Diagnostic Commands

Run these to diagnose the issue:

### Check Python and PySide6 versions
```bash
python --version
python -c "import PySide6; print(f'PySide6: {PySide6.__version__}')"
```

### Check Qt Library Path
```python
python -c "from PySide6.QtCore import QLibraryInfo; print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath))"
```

### List Installed Qt DLLs
```powershell
Get-ChildItem ".venv\Lib\site-packages\PySide6" -Filter Qt6*.dll
```

### Check for Missing Dependencies
```bash
# Install Dependency Walker (optional)
# Download from: https://www.dependencywalker.com/
# Use it to analyze Qt6Core.dll for missing dependencies
```

---

## Working Configuration (Tested on Windows)

If all else fails, use this tested configuration with specific package versions:

```bash
# Create fresh environment
uv venv --python 3.12

# Activate
.venv\Scripts\activate

# Install tested versions
uv pip install PySide6==6.6.3.1
uv pip install numpy==1.26.4
uv pip install scipy==1.11.4
uv pip install scikit-image==0.22.0
uv pip install opencv-python==4.9.0
uv pip install Pillow==10.2.0
uv pip install matplotlib==3.8.2
uv pip install PyYAML==6.0.1
uv pip install pyserial==3.5
uv pip install pytest==7.4.3
uv pip install pytest-cov==4.1.0
uv pip install pytest-mock==3.12.0
uv pip install pytest-qt==4.3.1
uv pip install pipython>=2.9.0
uv pip install pylint==3.0.3
uv pip install black==23.12.1
uv pip install mypy==1.8.0

# Or install from requirements.txt (recommended)
uv pip install -r requirements.txt
```

---

## Still Not Working?

### Post on GitHub Issues
If none of these solutions work, please provide:
1. **Windows version**: `winver` (Win+R, type winver)
2. **Python version**: `python --version`
3. **PySide6 version**: `pip show PySide6`
4. **Full error traceback**
5. **Output of diagnostic commands above**

### Quick Workaround: Use WSL2
As a last resort, you can run Kalib in WSL2 (Windows Subsystem for Linux):
1. Install WSL2: `wsl --install`
2. Install VcXsrv or X410 for GUI forwarding
3. Follow Linux installation instructions

---

## Prevention for Future Installations

### Best Practices for Windows
1. **Always install Visual C++ Redistributables first**
2. **Use Python 3.12 (or 3.11 if issues persist)**
3. **Pin PySide6 to tested version (6.6.3.1 or 6.8.0.2)**
4. **Use UV for faster, more reliable installations**
5. **Keep environment isolated** - don't install other Qt tools in same environment

### Requirements File Best Practice
Always specify exact versions for production stability:
```txt
# requirements.txt
PySide6==6.8.0.2  # Instead of PySide6>=6.5.0
```

---

**Last Updated**: 2026-02-04
**Tested On**: Windows 10 22H2, Windows 11 23H2

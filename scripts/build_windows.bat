@echo off
REM Windows构建脚本：打包robolabel为Windows可执行程序
REM 产物：dist\robolabel\robolabel.exe（onedir模式，双击即用）

echo ========================================
echo Building robolabel for Windows
echo ========================================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found in PATH
    exit /b 1
)

REM 检查PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Error: PyInstaller not installed. Run: pip install pyinstaller
    exit /b 1
)

REM 清理旧构建产物
echo Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist\robolabel rmdir /s /q dist\robolabel

REM 执行打包
echo Running PyInstaller...
python -m PyInstaller robolabel-win.spec --clean --noconfirm

if errorlevel 1 (
    echo Build failed!
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo Product: dist\robolabel\robolabel.exe
echo.
echo To test: cd dist\robolabel ^&^& robolabel.exe
echo.

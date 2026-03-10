@echo off
chcp 65001 >nul
echo.
echo =========================================
echo      躺平进度条 - 打包工具
echo =========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检查 Python 版本...
python --version
echo.

echo [2/4] 安装依赖...
pip install -U pystray Pillow python-dateutil plyer win10toast-click pyinstaller
if errorlevel 1 (
    echo [错误] 安装依赖失败
    pause
    exit /b 1
)
echo.

echo [3/4] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "躺平进度条.spec" del /f /q "躺平进度条.spec"
echo.

echo [4/4] 构建 exe...
pyinstaller --onefile --noconsole ^
    --name="躺平进度条" ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=dateutil ^
    --hidden-import=plyer ^
    --hidden-import=win10toast_click ^
    retirement_tray.py

if errorlevel 1 (
    echo.
    echo [错误] 构建失败
    pause
    exit /b 1
)

echo.
echo =========================================
echo      构建成功!
echo =========================================
echo.
echo 输出文件: dist\躺平进度条.exe
echo.
pause

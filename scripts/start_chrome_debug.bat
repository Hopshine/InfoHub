@echo off
echo 正在以调试模式启动Chrome...
echo.
echo 注意：这将关闭所有现有的Chrome窗口！
echo 按任意键继续，或关闭此窗口取消...
pause >nul

REM 关闭现有Chrome进程
taskkill /F /IM chrome.exe >nul 2>&1

REM 等待进程完全关闭
timeout /t 2 /nobreak >nul

REM 以调试模式启动Chrome
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data"

echo.
echo Chrome已以调试模式启动（端口9222）
echo 现在可以运行采集程序了
echo.
pause

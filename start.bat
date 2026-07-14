@echo off
title BidBuddy - 招投标AI助手
echo.
echo    ╔══════════════════════════════════════╗
echo    ║       BidBuddy - 招投标AI助手        ║
echo    ║       极简 · 智能 · 高效              ║
echo    ╚══════════════════════════════════════╝
echo.
echo [*] 正在检查依赖...
pip install -r requirements.txt -q
echo.
echo [*] 启动服务...
echo [*] 浏览器打开: http://localhost:8080
echo.
start http://localhost:8080
python app.py
pause

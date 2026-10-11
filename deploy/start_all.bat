@echo off
chcp 65001 >nul
echo ========================================================
echo   Gate BTC/ETH 五分钟涨跌统计与预测系统 (v3.0)
echo   单机长期无人值守 · 决策悬浮弹窗 + 完整控制台
echo ========================================================

echo [1/3] 正在检查数据库与基础数据初始化...
py -3.13 deploy\mock_simulator.py

echo [2/3] 正在启动后端服务 (FastAPI + WebSocket)...
start "Gate Dual Odds Engine Backend" py -3.13 deploy\start_backend.py

timeout /t 2 /nobreak >nul

echo [3/3] 正在唤起置顶决策悬浮弹窗...
py -3.13 deploy\start_popup.py

echo.
echo 系统已成功启动！
echo 完整 Web 控制台访问地址: http://127.0.0.1:8000/static/index.html
echo 置顶决策悬浮弹窗地址:   http://127.0.0.1:8000/static/popup.html
echo API 接口文档:           http://127.0.0.1:8000/docs
echo ========================================================
pause

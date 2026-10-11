"""
置顶决策悬浮弹窗桌面启动脚本
严格按第十六章 16.4~16.7 节落地：
以独立应用小窗模式 (--app) 启动置顶弹窗，悬浮于 Gate 交易页面之上
"""

import sys
import webbrowser
import subprocess
from backend.app.config import settings

def launch_popup_window():
    popup_url = f"http://{settings.HOST}:{settings.PORT}/static/popup.html"
    print(f"正在唤起置顶决策弹窗: {popup_url}")

    # 尝试使用 Edge/Chrome 的 --app 模式启动独立置顶无边框小窗口
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    
    launched = False
    for browser_exe in chrome_paths:
        try:
            # 启动 480x640 独立悬浮小窗口
            cmd = [browser_exe, f"--app={popup_url}", "--window-size=500,680"]
            subprocess.Popen(cmd)
            launched = True
            print(f"已通过独立置顶应用窗模式启动 ({browser_exe})")
            break
        except Exception:
            continue

    if not launched:
        print("未检测到独立浏览器快捷命令，通过默认浏览器打开...")
        webbrowser.open(popup_url)

if __name__ == "__main__":
    launch_popup_window()

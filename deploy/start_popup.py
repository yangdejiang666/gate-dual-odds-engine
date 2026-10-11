"""
置顶决策悬浮弹窗桌面启动脚本
严格按第十六章 16.4~16.7 节落地：
以独立应用小窗模式 (--app) 启动置顶弹窗，悬浮于 Gate 交易页面之上
支持动态读取当前后端实际活跃端口
"""

import sys
import webbrowser
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings

def get_current_port() -> int:
    port_file = settings.DATA_DIR / "active_port.txt"
    if port_file.exists():
        try:
            with open(port_file, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            pass
    return settings.PORT

def launch_popup_window():
    port = get_current_port()
    popup_url = f"http://{settings.HOST}:{port}/static/popup.html"
    print(f"正在唤起置顶决策弹窗: {popup_url}")

    # 尝试使用 Edge/Chrome 的 --app 模式启动独立置顶无边框小窗口
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能针灸辨证选穴助手 - 快速启动器
双击此文件即可启动程序并自动打开浏览器
"""

import os
import sys
import subprocess
import webbrowser
import time
import threading
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import uvicorn
        import fastapi
        return True
    except ImportError as e:
        print(f"缺少依赖: {e}")
        print("正在安装依赖...")
        subprocess.call([sys.executable, "-m", "pip", "install", "uvicorn", "fastapi"])
        return True

def start_server():
    """启动服务器"""
    print("🚀 启动智能针灸辨证选穴助手...")
    print("服务器启动中，请稍候...")

    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # 启动服务器
    subprocess.call([sys.executable, "app.py"])

def auto_open_browser():
    """自动打开浏览器"""
    time.sleep(3)  # 等待服务器启动
    print("🌐 正在打开浏览器...")
    webbrowser.open("http://localhost:8000")

def main():
    """主函数"""
    print("=" * 50)
    print("    智能针灸辨证选穴助手 - 快速启动器")
    print("=" * 50)

    # 检查依赖
    if not check_dependencies():
        input("按回车键退出...")
        return

    # 询问是否自动打开浏览器
    response = input("是否自动打开浏览器？(y/n): ").lower()
    auto_open = response.startswith('y')

    # 在新线程中启动浏览器
    if auto_open:
        browser_thread = threading.Thread(target=auto_open_browser)
        browser_thread.daemon = True
        browser_thread.start()

    # 启动服务器
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n\n👋 服务器已关闭")

    if auto_open:
        input("按回车键退出...")
    else:
        input("\n按回车键关闭服务器...")

if __name__ == "__main__":
    main()
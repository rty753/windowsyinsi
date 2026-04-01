#!/usr/bin/env python3
"""
Windows 隐私卫士 - 隐私设备监控与管理工具
Privacy Guard - Windows Privacy Device Monitor & Manager

需要管理员权限运行以控制设备和服务。
"""

import ctypes
import sys
import os

# Ensure the script directory is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def is_admin():
    """Check if the current process has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Re-launch the script with admin privileges via UAC prompt."""
    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
    except Exception as e:
        print(f"提权失败: {e}")
        input("按回车键退出...")
        sys.exit(1)


def main():
    if not is_admin():
        print("需要管理员权限, 正在请求提权...")
        run_as_admin()
        sys.exit(0)

    # Import and run the app
    from ui.app import PrivacyGuardApp
    app = PrivacyGuardApp()
    app.run()


if __name__ == "__main__":
    main()

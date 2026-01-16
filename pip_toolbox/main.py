"""
Python Pip 包管理器
主入口模块
"""
import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os

from . import state
from . import pip_utils
from . import handlers
from . import gui_components


def initial_load():
    """加载初始包列表并填充表格。"""
    state.status_label.config(text="正在加载已安装的包列表...")
    handlers.update_log("正在加载已安装的包列表...")
    handlers.disable_buttons()
    handlers.refresh_package_list_threaded()


def main():
    """主入口函数。"""
    # 设置 GUI
    root = gui_components.setup_gui()
    
    # 延迟加载初始数据
    root.after(100, initial_load)
    
    # 运行主循环
    root.mainloop()


if __name__ == "__main__":
    # 检查 packaging 库
    try:
        from packaging.version import parse
    except ImportError:
        messagebox.showerror(
            "缺少库",
            "需要 'packaging' 库来进行版本比较。\n请尝试运行: pip install packaging"
        )
        sys.exit(1)
    
    # 检查 pip 可用性
    try:
        proc = subprocess.run(
            [pip_utils.PIP_COMMAND.split()[0], "--version"],
            check=True, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        print(f"使用 pip: {proc.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        messagebox.showerror(
            "Pip 错误",
            f"无法执行 '{pip_utils.PIP_COMMAND}'。\n"
            f"请确保 Python 和 pip 已正确安装并位于系统 PATH 中。\n\n错误详情: {e}"
        )
        sys.exit(1)
    
    main()

"""
状态管理模块
包含所有 GUI 组件和全局状态变量的引用
"""
import tkinter as tk

# --- 全局状态变量 ---
all_packages = []
version_comboboxes = {}
outdated_packages_data = None  # 存储 [(name, installed_ver, latest_ver)]
current_view_mode = "all"  # "all" 或 "outdated"
checking_updates_thread = None  # 用于管理检查线程

# --- GUI 组件引用 (在 gui_components.py 中初始化) ---
root = None
tree = None
search_var = None
package_count_label = None
status_label = None
log_display_area = None
log_frame = None
log_visible_var = None
status_bar = None

# --- 按钮引用 ---
install_button = None
uninstall_button = None
change_source_button = None
check_updates_button = None
toggle_view_button = None
update_all_button = None
clear_log_button = None

"""
GUI 组件模块
包含所有 GUI 组件的创建和事件绑定
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys

from . import state
from . import handlers
from . import pip_utils


def create_main_window():
    """创建并配置主窗口。"""
    state.root = tk.Tk()
    state.root.title(f"Python Pip 包管理器 (Using: {os.path.basename(pip_utils.PIP_COMMAND)})")
    
    sw = state.root.winfo_screenwidth()
    sh = state.root.winfo_screenheight()
    w = int(sw * 0.31)
    h = int(sh * 0.7)
    state.root.geometry(f"{w}x{h}+200+100")
    
    # 样式配置
    style = ttk.Style()
    try:
        if os.name == 'nt':
            style.theme_use('vista')
        elif sys.platform == 'darwin':
            style.theme_use('aqua')
        else:
            style.theme_use('clam')
    except tk.TclError:
        print("注意: 选择的 ttk 主题不可用，使用默认。")
    
    style.configure('Toolbutton', font=('Segoe UI', 9) if os.name == 'nt' else ('Sans', 9))
    
    return state.root


def create_top_frame():
    """创建顶部搜索框架。"""
    top_frame = ttk.Frame(state.root, padding="10 5 10 5")
    top_frame.pack(fill="x")
    
    ttk.Label(top_frame, text="搜索包:").pack(side="left")
    
    state.search_var = tk.StringVar()
    search_entry = ttk.Entry(top_frame, textvariable=state.search_var, width=30)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)
    search_entry.bind("<KeyRelease>", handlers.search_packages)
    
    state.package_count_label = ttk.Label(top_frame, text="包数量: 0", width=20, anchor='e')
    state.package_count_label.pack(side="right", padx=(5, 0))
    
    return top_frame


def create_tree_frame():
    """创建表格框架。"""
    tree_frame = ttk.Frame(state.root, padding="10 5 10 5")
    tree_frame.pack(fill="both", expand=True)
    
    columns = ("name", "version")
    state.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    state.tree.heading("name", text="包名称", anchor="w")
    state.tree.heading("version", text="版本信息", anchor="w")
    state.tree.column("name", width=350, stretch=tk.YES, anchor="w")
    state.tree.column("version", width=200, stretch=tk.YES, anchor="w")
    
    tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=state.tree.yview)
    state.tree.configure(yscrollcommand=tree_scrollbar.set)
    tree_scrollbar.pack(side="right", fill="y")
    state.tree.pack(side="left", fill="both", expand=True)
    
    return tree_frame, tree_scrollbar


def create_button_frame():
    """创建按钮框架。"""
    button_frame = ttk.Frame(state.root, padding="10 5 10 10")
    button_frame.pack(fill="x")
    
    state.install_button = ttk.Button(button_frame, text="安装/更新选定版本", command=handlers.install_selected_version)
    state.install_button.pack(side="left", padx=(0, 5))
    
    state.uninstall_button = ttk.Button(button_frame, text="卸载选定包", command=handlers.uninstall_selected_package)
    state.uninstall_button.pack(side="left", padx=5)
    
    ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side="left", fill='y', padx=10, pady=2)
    
    state.check_updates_button = ttk.Button(button_frame, text="检查更新", command=handlers.check_for_updates)
    state.check_updates_button.pack(side="left", padx=5)
    
    state.toggle_view_button = ttk.Button(button_frame, text="仅显示过时包", command=handlers.toggle_outdated_view, state="disabled")
    state.toggle_view_button.pack(side="left", padx=5)
    
    ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side="left", fill='y', padx=10, pady=2)
    
    state.update_all_button = ttk.Button(button_frame, text="全部更新", command=handlers.update_all_packages, state="disabled")
    state.update_all_button.pack(side="left", padx=5)
    
    state.change_source_button = ttk.Button(button_frame, text="更改 Pip 源", command=handlers.change_source)
    state.change_source_button.pack(side="right", padx=(5, 0))
    
    return button_frame


def create_status_bar():
    """创建状态栏。"""
    state.status_bar = ttk.Frame(state.root, relief=tk.SUNKEN, borderwidth=1, padding=0)
    state.status_bar.pack(side="bottom", fill="x")
    
    state.status_label = ttk.Label(state.status_bar, text="就绪.", anchor='w', padding=(5, 2, 5, 2))
    state.status_label.pack(side="left", fill="x", expand=True)
    
    state.log_visible_var = tk.BooleanVar(value=True)
    log_toggle_checkbutton = ttk.Checkbutton(
        state.status_bar, text="日志", variable=state.log_visible_var,
        command=handlers.toggle_log_display, style='Toolbutton'
    )
    log_toggle_checkbutton.pack(side="right", padx=(0, 2), pady=1)
    
    state.clear_log_button = ttk.Button(state.status_bar, text="清空", command=handlers.clear_log, width=5, style='Toolbutton')
    
    return state.status_bar


def create_log_frame():
    """创建日志显示区域。"""
    state.log_frame = ttk.Frame(state.root, height=150, relief=tk.GROOVE, borderwidth=1)
    
    state.log_display_area = scrolledtext.ScrolledText(
        state.log_frame, wrap=tk.WORD, height=8, state=tk.DISABLED,
        relief=tk.FLAT, bd=0,
        font=("Consolas", 9) if os.name == 'nt' else ("Monospace", 9)
    )
    state.log_display_area.pack(side="top", fill="both", expand=True, padx=1, pady=1)
    
    return state.log_frame


def bind_events(tree_scrollbar):
    """绑定所有事件处理程序。"""
    state.tree.bind("<<TreeviewSelect>>", on_tree_select)
    state.tree.bind("<Configure>", update_combobox_position)
    state.root.bind("<Configure>", update_combobox_position)
    tree_scrollbar.bind("<B1-Motion>", lambda e: state.root.after(50, update_combobox_position))
    state.root.bind_all("<MouseWheel>", lambda e: state.root.after(50, update_combobox_position))
    state.tree.bind("<Up>", lambda e: state.root.after(50, update_combobox_position))
    state.tree.bind("<Down>", lambda e: state.root.after(50, update_combobox_position))
    state.tree.bind("<Prior>", lambda e: state.root.after(50, update_combobox_position))
    state.tree.bind("<Next>", lambda e: state.root.after(50, update_combobox_position))


def on_tree_select(event):
    """处理 Treeview 中的选择变化，放置/更新组合框。"""
    import threading
    
    selected_items = state.tree.selection()
    if not selected_items:
        for widget in state.version_comboboxes.values():
            if widget and widget.winfo_ismapped():
                widget.place_forget()
        return
    
    item_id = selected_items[0]
    
    for row_id, widget in list(state.version_comboboxes.items()):
        if widget and row_id != item_id:
            try:
                if widget.winfo_exists():
                    widget.place_forget()
            except tk.TclError:
                pass
    
    existing_combobox = state.version_comboboxes.get(item_id)
    if existing_combobox and not existing_combobox.winfo_exists():
        existing_combobox = None
        state.version_comboboxes[item_id] = None
    
    try:
        if not state.tree.exists(item_id):
            return
        pkg_name, _ = state.tree.item(item_id, "values")
    except tk.TclError:
        return
    
    if not existing_combobox:
        combobox = ttk.Combobox(state.tree, state="disabled", exportselection=False)
        state.version_comboboxes[item_id] = combobox
    else:
        combobox = existing_combobox
    
    combobox.set("正在查询版本...")
    combobox.configure(state="disabled")
    state.root.after(10, _place_combobox, item_id, combobox, pkg_name)


def _place_combobox(item_id, combobox, pkg_name):
    """放置组合框并开始获取版本。"""
    import threading
    
    try:
        if not combobox.winfo_exists():
            return
        if not state.tree.exists(item_id):
            return
        bbox = state.tree.bbox(item_id, column=1)
        if bbox:
            x, y, width, height = bbox
            combobox.place(x=x, y=y, width=width, height=height)
            threading.Thread(target=_fetch_versions, args=(pkg_name, combobox), daemon=True).start()
        else:
            combobox.place_forget()
    except tk.TclError as e:
        print(f"为 {pkg_name} 放置组合框出错: {e}")
        try:
            if combobox.winfo_exists():
                combobox.place_forget()
        except tk.TclError:
            pass


def _fetch_versions(pkg_name, combobox):
    """为包获取可用版本（由组合框使用）。"""
    available_versions_str, parsed_versions = pip_utils.fetch_available_versions(pkg_name)
    
    current_installed_version = next((v for p, v in state.all_packages if p == pkg_name), None)
    latest_known_version = next(
        (latest for name, _, latest in state.outdated_packages_data if name == pkg_name), None
    ) if state.outdated_packages_data else None
    
    display_versions = []
    found_installed = False
    best_match_index = 0
    
    for i, v_str in enumerate(available_versions_str):
        label = v_str
        if not v_str.startswith("错误:") and not v_str.startswith("查询") and not v_str.startswith("未找到"):
            is_current = (v_str == current_installed_version)
            is_latest = (latest_known_version is not None and v_str == latest_known_version)
            if is_current:
                label += " (当前)"
                found_installed = True
                best_match_index = i
            if is_latest and not is_current:
                label += " (最新)"
                if not found_installed:
                    best_match_index = i
        display_versions.append(label)
    
    try:
        if combobox.winfo_exists():
            combobox.configure(state="readonly")
            combobox["values"] = display_versions
            combobox.set(display_versions[best_match_index] if display_versions else "无可用版本")
    except tk.TclError:
        print(f"信息: 为 {pkg_name} 的组合框在设置版本前已被销毁。")


def update_combobox_position(event=None):
    """当视图变化时更新活动组合框的位置。"""
    state.root.after_idle(_do_update_combobox_position)


def _do_update_combobox_position():
    """更新组合框位置的实际工作。"""
    selected_items = state.tree.selection()
    if not selected_items:
        for row_id, widget in list(state.version_comboboxes.items()):
            if widget and widget.winfo_ismapped():
                widget.place_forget()
        return
    
    item_id = selected_items[0]
    combobox = state.version_comboboxes.get(item_id)
    
    try:
        if combobox and combobox.winfo_exists():
            if not state.tree.exists(item_id):
                combobox.place_forget()
                if state.version_comboboxes.get(item_id) == combobox:
                    state.version_comboboxes[item_id] = None
                return
            bbox = state.tree.bbox(item_id, column=1)
            if bbox:
                x, y, width, height = bbox
                current_info = combobox.place_info()
                if (str(x) != current_info.get('x') or
                    str(y) != current_info.get('y') or
                    str(width) != current_info.get('width') or
                    str(height) != current_info.get('height')):
                    combobox.place(x=x, y=y, width=width, height=height)
            else:
                combobox.place_forget()
    except tk.TclError:
        pass


def setup_gui():
    """设置完整的 GUI 并返回 root 窗口。"""
    create_main_window()
    create_top_frame()
    tree_frame, tree_scrollbar = create_tree_frame()
    create_button_frame()
    create_status_bar()
    create_log_frame()
    bind_events(tree_scrollbar)
    handlers.toggle_log_display()  # 启动时显示日志
    
    return state.root

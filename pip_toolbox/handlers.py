"""
事件处理模块
包含按钮事件处理、表格操作、更新检查等功能
"""
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import time
from packaging.version import parse as parse_version

from . import pip_utils
from . import state


def populate_table(packages_to_display=None, view_mode="all"):
    """根据视图模式用包数据填充 Treeview 表格。"""
    clear_comboboxes()
    state.tree.delete(*state.tree.get_children())
    
    if packages_to_display is None:
        if view_mode == "outdated" and state.outdated_packages_data:
            packages_to_display = [(name, installed) for name, installed, latest in state.outdated_packages_data]
        else:
            packages_to_display = state.all_packages
    
    for pkg_name, pkg_version in packages_to_display:
        row_id = state.tree.insert("", "end", values=(pkg_name, pkg_version))
        state.version_comboboxes[row_id] = None
    
    count = len(packages_to_display)
    count_prefix = "过时包数量: " if view_mode == "outdated" else "包数量: "
    state.package_count_label.config(text=f"{count_prefix}{count}")
    
    if view_mode == "outdated":
        state.toggle_view_button.config(text="显示所有包")
        if state.update_all_button and state.update_all_button.winfo_exists():
            state.update_all_button.config(state="normal" if state.outdated_packages_data else "disabled")
    else:
        state.toggle_view_button.config(text="仅显示过时包")
        if state.update_all_button and state.update_all_button.winfo_exists():
            state.update_all_button.config(state="disabled")
    
    search_packages()


def clear_comboboxes():
    """销毁任何活动的版本选择组合框。"""
    for widget in list(state.version_comboboxes.values()):
        if widget:
            try:
                widget.destroy()
            except tk.TclError:
                pass
    state.version_comboboxes.clear()


def search_packages(event=None):
    """基于搜索查询过滤表格中当前显示的包。"""
    query = state.search_var.get().strip().lower()
    
    if state.current_view_mode == "outdated":
        base_packages_data = state.outdated_packages_data or []
        base_packages_list = [(name, installed) for name, installed, latest in base_packages_data]
    else:
        base_packages_list = state.all_packages
    
    if query:
        filtered_packages = [pkg for pkg in base_packages_list if query in pkg[0].lower()]
    else:
        filtered_packages = base_packages_list
    
    _populate_table_internal(filtered_packages, state.current_view_mode)


def _populate_table_internal(packages_list, view_mode):
    """内部辅助函数，用于更新表格而不更改全局视图状态。"""
    clear_comboboxes()
    state.tree.delete(*state.tree.get_children())
    
    for pkg_name, pkg_version in packages_list:
        row_id = state.tree.insert("", "end", values=(pkg_name, pkg_version))
        state.version_comboboxes[row_id] = None
    
    count = len(packages_list)
    count_prefix = "过时包数量: " if view_mode == "outdated" else "包数量: "
    search_active = state.search_var.get().strip() != ""
    filter_text = "(搜索中) " if search_active else ""
    state.package_count_label.config(text=f"{count_prefix}{filter_text}{count}")


def install_selected_version():
    """安装组合框中选定的版本。"""
    selected_items = state.tree.selection()
    if not selected_items:
        messagebox.showwarning("未选择", "请在表格中选择一个包。")
        return
    
    item_id = selected_items[0]
    try:
        pkg_name, displayed_version = state.tree.item(item_id, "values")
    except tk.TclError:
        messagebox.showerror("错误", "无法获取所选项目的信息 (可能已删除)。")
        return
    
    combobox = state.version_comboboxes.get(item_id)
    if not combobox or not combobox.winfo_exists() or combobox.cget('state') == 'disabled':
        messagebox.showwarning("未加载版本", f"请等待 '{pkg_name}' 的版本加载或选择完成。")
        return
    
    selected_value = combobox.get()
    version_to_install = selected_value.split(" ")[0].strip()
    
    if not version_to_install or version_to_install.startswith("错误") or \
       version_to_install.startswith("查询") or version_to_install == "未找到版本":
        messagebox.showerror("无法安装", f"无法安装选定的条目: '{selected_value}'")
        return
    
    current_version = next((v for p, v in state.all_packages if p == pkg_name), None)
    action = "安装"
    prompt = f"确定要安装 {pkg_name}=={version_to_install} 吗？"
    
    if current_version:
        try:
            v_install_parsed = parse_version(version_to_install)
            v_current_parsed = parse_version(current_version)
            if v_install_parsed == v_current_parsed:
                action = "重新安装"
                prompt = f"{pkg_name} 版本 {version_to_install} 已安装。\n是否要重新安装？"
            elif v_install_parsed > v_current_parsed:
                action = "更新到"
                prompt = f"确定要将 {pkg_name} 从 {current_version} 更新到 {version_to_install} 吗？"
            else:
                action = "降级到"
                prompt = f"确定要将 {pkg_name} 从 {current_version} 降级到 {version_to_install} 吗？"
        except Exception as e:
            print(f"警告: 无法解析版本进行比较: {e}。使用默认提示。")
            action = "安装/更改"
            prompt = f"确定要安装/更改到 {pkg_name}=={version_to_install} 吗？"
    
    if messagebox.askyesno(f"{action}确认", prompt):
        target_package = f"{pkg_name}=={version_to_install}"
        command = [pip_utils.PIP_COMMAND, "install", "--upgrade", "--no-cache-dir", target_package]
        run_pip_command_threaded(command, f"{action} {target_package}")


def uninstall_selected_package():
    """卸载选定的包。"""
    selected_items = state.tree.selection()
    if not selected_items:
        messagebox.showwarning("未选择", "请在表格中选择要卸载的包。")
        return
    
    item_id = selected_items[0]
    try:
        pkg_name = state.tree.item(item_id, "values")[0]
    except tk.TclError:
        messagebox.showerror("错误", "无法获取所选项目的信息 (可能已删除)。")
        return
    
    if messagebox.askyesno("卸载确认", f"确定要卸载 {pkg_name} 吗？"):
        command = [pip_utils.PIP_COMMAND, "uninstall", "-y", pkg_name]
        run_pip_command_threaded(command, f"卸载 {pkg_name}")


def update_all_packages():
    """将所有过时包更新到最新版本。"""
    if not state.outdated_packages_data:
        messagebox.showinfo("无过时包", "当前没有过时包需要更新。")
        return
    
    if messagebox.askyesno("全部更新确认", f"确定要将 {len(state.outdated_packages_data)} 个过时包更新到最新版本吗？"):
        disable_buttons()
        update_log(f"⏳ 开始更新 {len(state.outdated_packages_data)} 个过时包...\n")
        thread = threading.Thread(
            target=_update_all_packages_threaded,
            args=(state.outdated_packages_data,),
            daemon=True
        )
        thread.start()


def _update_all_packages_threaded(outdated_packages):
    """在线程中批量更新所有过时包。"""
    success = True
    total = len(outdated_packages)
    
    for i, (pkg_name, installed_version, latest_version) in enumerate(outdated_packages):
        target_package = f"{pkg_name}=={latest_version}"
        command = [pip_utils.PIP_COMMAND, "install", "--upgrade", "--no-cache-dir", target_package]
        action_name = f"更新 {pkg_name} 到 {latest_version}"
        
        state.root.after(0, update_log, f"⏳ ({i+1}/{total}) {action_name}...\n   命令: {' '.join(command)}\n")
        
        try:
            import subprocess
            import os
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout, stderr = process.communicate(timeout=600)
            
            if process.returncode == 0:
                state.root.after(0, update_log, f"✅ ({i+1}/{total}) {action_name} 成功。\n--- 输出 ---\n{stdout}\n")
                if stderr:
                    state.root.after(0, update_log, f"--- 警告/信息 ---\n{stderr}\n")
            else:
                success = False
                state.root.after(0, update_log, f"❌ ({i+1}/{total}) {action_name} 失败 (Code: {process.returncode}).\n--- 输出 ---\n{stdout}\n--- 错误 ---\n{stderr}\n")
        except subprocess.TimeoutExpired:
            success = False
            state.root.after(0, update_log, f"⌛ ({i+1}/{total}) {action_name} 超时 (超过10分钟)。\n")
            try:
                process.kill()
                stdout, stderr = process.communicate()
                state.root.after(0, update_log, f"--- 最后输出 ---\n{stdout}\n--- 最后错误 ---\n{stderr}\n")
            except Exception as kill_e:
                state.root.after(0, update_log, f"--- 尝试终止超时进程时出错: {kill_e} ---\n")
        except Exception as e:
            success = False
            state.root.after(0, update_log, f"❌ ({i+1}/{total}) 执行 {action_name} 时发生意外错误: {str(e)}\n")
    
    state.root.after(0, command_finished, f"✅ 全部更新完成 ({total} 个包)。\n", success)


def run_pip_command_threaded(command, action_name):
    """在单独线程中运行 pip 命令并更新日志。"""
    disable_buttons()
    update_log(f"⏳ {action_name}...\n   命令: {' '.join(command)}\n")
    
    def callback(log_message, success):
        state.root.after(0, command_finished, log_message, success)
    
    thread = threading.Thread(
        target=pip_utils.run_pip_command_sync,
        args=(command, action_name, callback),
        daemon=True
    )
    thread.start()


def command_finished(log_message, needs_refresh):
    """pip 命令完成后更新 GUI。"""
    update_log(log_message)
    
    if needs_refresh:
        update_log("🔄 正在刷新已安装包列表...\n")
        state.outdated_packages_data = None
        
        try:
            if state.toggle_view_button and state.toggle_view_button.winfo_exists():
                state.toggle_view_button.config(state="disabled")
            if state.update_all_button and state.update_all_button.winfo_exists():
                state.update_all_button.config(state="disabled")
        except (tk.TclError, NameError):
            pass
        
        state.status_label.config(text="包列表已更改，请重新检查更新。")
        refresh_package_list_threaded()
    else:
        enable_buttons()
        update_log("🔴 操作未成功完成或无需刷新列表。\n")


def refresh_package_list_threaded():
    """在后台线程中获取更新的包列表。"""
    try:
        state.all_packages = pip_utils.get_installed_packages()
        log_msg = "✅ 包列表刷新完成。\n"
        success = True
    except Exception as e:
        log_msg = f"❌ 刷新包列表时出错: {e}\n"
        success = False
    
    state.root.after(0, _update_gui_after_refresh, log_msg, success)


def _update_gui_after_refresh(log_msg, success):
    """刷新后更新表格并启用按钮。"""
    update_log(log_msg)
    
    if success:
        state.current_view_mode = "all"
        populate_table(view_mode="all")
        state.status_label.config(text=f"包列表已刷新 ({len(state.all_packages)} 个包)。")
    else:
        state.status_label.config(text="刷新包列表失败。")
    
    enable_buttons()
    
    try:
        if state.toggle_view_button and state.toggle_view_button.winfo_exists():
            state.toggle_view_button.config(state="disabled")
        if state.update_all_button and state.update_all_button.winfo_exists():
            state.update_all_button.config(state="disabled")
    except (tk.TclError, NameError):
        pass


def disable_buttons():
    """在操作期间禁用按钮。"""
    buttons = [
        state.install_button, state.uninstall_button, state.change_source_button,
        state.check_updates_button, state.toggle_view_button, state.update_all_button
    ]
    for btn in buttons:
        try:
            if btn and btn.winfo_exists():
                btn.config(state="disabled")
        except (tk.TclError, NameError):
            pass


def enable_buttons():
    """操作后重新启用按钮。"""
    try:
        if state.install_button and state.install_button.winfo_exists():
            state.install_button.config(state="normal")
        if state.uninstall_button and state.uninstall_button.winfo_exists():
            state.uninstall_button.config(state="normal")
        if state.change_source_button and state.change_source_button.winfo_exists():
            state.change_source_button.config(state="normal")
        if state.check_updates_button and state.check_updates_button.winfo_exists():
            state.check_updates_button.config(state="normal")
        if state.toggle_view_button and state.toggle_view_button.winfo_exists():
            state.toggle_view_button.config(state="normal" if state.outdated_packages_data else "disabled")
        if state.update_all_button and state.update_all_button.winfo_exists():
            state.update_all_button.config(
                state="normal" if state.current_view_mode == "outdated" and state.outdated_packages_data else "disabled"
            )
    except (tk.TclError, NameError):
        pass


def update_log(message):
    """将消息追加到日志显示区域。"""
    if not state.log_display_area or not state.log_display_area.winfo_exists():
        return
    try:
        state.log_display_area.config(state=tk.NORMAL)
        state.log_display_area.insert(tk.END, message + "\n")
        state.log_display_area.see(tk.END)
        state.log_display_area.config(state=tk.DISABLED)
    except tk.TclError as e:
        print(f"更新日志出错: {e}")


def clear_log():
    """清除日志显示区域。"""
    if not state.log_display_area or not state.log_display_area.winfo_exists():
        return
    try:
        state.log_display_area.config(state=tk.NORMAL)
        state.log_display_area.delete('1.0', tk.END)
        state.log_display_area.config(state=tk.DISABLED)
    except tk.TclError:
        pass


def change_source():
    """允许更改 pip 索引 URL。"""
    current_src = pip_utils.get_current_source()
    new_source = simpledialog.askstring(
        "更改 Pip 源",
        f"当前源: {current_src}\n\n输入新的 PyPI 索引 URL (留空则重置):",
        initialvalue="https://pypi.tuna.tsinghua.edu.cn/simple"
    )
    
    if new_source is None:
        return
    
    if not new_source.strip():
        if messagebox.askyesno("重置确认", "确定要移除自定义源设置，恢复默认吗？"):
            update_log("正在尝试移除自定义源...")
            success = False
            try:
                import subprocess
                import os
                cmd_global = [pip_utils.PIP_COMMAND, "config", "unset", "global.index-url"]
                cmd_user = [pip_utils.PIP_COMMAND, "config", "unset", "user.index-url"]
                subprocess.run(cmd_global, capture_output=True, check=False,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                subprocess.run(cmd_user, capture_output=True, check=False,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                success = True
                messagebox.showinfo("源已重置", "已尝试移除自定义源配置。")
                update_log("✅ 源配置已尝试重置。")
            except Exception as e:
                messagebox.showerror("错误", f"移除源时出错: {e}")
                update_log(f"❌ 移除源时出错: {e}")
            
            if success:
                state.outdated_packages_data = None
                try:
                    if state.toggle_view_button and state.toggle_view_button.winfo_exists():
                        state.toggle_view_button.config(state="disabled")
                    if state.update_all_button and state.update_all_button.winfo_exists():
                        state.update_all_button.config(state="disabled")
                except (tk.TclError, NameError):
                    pass
                state.status_label.config(text="源已更改，请重新检查更新。")
        return
    
    if not (new_source.startswith("http://") or new_source.startswith("https://")):
        messagebox.showerror("格式错误", "源地址必须以 http:// 或 https:// 开头。")
        return
    
    state.outdated_packages_data = None
    try:
        if state.toggle_view_button and state.toggle_view_button.winfo_exists():
            state.toggle_view_button.config(state="disabled")
        if state.update_all_button and state.update_all_button.winfo_exists():
            state.update_all_button.config(state="disabled")
    except (tk.TclError, NameError):
        pass
    
    state.status_label.config(text="源已更改，请重新检查更新。")
    command = [pip_utils.PIP_COMMAND, "config", "set", "global.index-url", new_source]
    action_name = f"设置新源为 {new_source}"
    run_pip_command_threaded(command, action_name)
    messagebox.showinfo("正在换源", f"已开始尝试将 pip 源设置为: {new_source}\n请查看下方日志了解结果。")


def toggle_log_display():
    """显示或隐藏日志显示区域。"""
    if state.log_visible_var.get():
        state.log_frame.pack(side="bottom", fill="x", padx=5, pady=(0, 0), before=state.status_bar)
        try:
            if state.clear_log_button and state.clear_log_button.winfo_exists():
                state.clear_log_button.pack(in_=state.status_bar, side="right", padx=(0, 5), pady=1)
        except (tk.TclError, NameError):
            pass
    else:
        state.log_frame.pack_forget()
        try:
            if state.clear_log_button and state.clear_log_button.winfo_exists():
                state.clear_log_button.pack_forget()
        except (tk.TclError, NameError):
            pass


# --- 过时包逻辑 ---
def check_for_updates():
    """在当前视图中启动检查过时包的过程（尊重任何活跃过滤）。"""
    if state.checking_updates_thread and state.checking_updates_thread.is_alive():
        messagebox.showinfo("请稍候", "已经在检查更新了。")
        return
    
    packages_to_check = []
    displayed_item_ids = state.tree.get_children()
    
    if not displayed_item_ids:
        messagebox.showinfo("无包显示", "表格中当前没有显示任何包可供检查。")
        return
    
    for item_id in displayed_item_ids:
        try:
            pkg_name, pkg_version = state.tree.item(item_id, "values")
            packages_to_check.append((pkg_name, pkg_version))
        except tk.TclError:
            print(f"警告: 无法获取项 {item_id} 的值，跳过。")
            continue
    
    if not packages_to_check:
        messagebox.showinfo("无包", "无法获取表格中显示的包信息。")
        return
    
    is_filtered_check = len(packages_to_check) < len(state.all_packages)
    check_scope_message = f"当前视图中的 {len(packages_to_check)} 个包" if is_filtered_check else f"所有 {len(state.all_packages)} 个已安装包"
    status_suffix = " (筛选后)" if is_filtered_check else ""
    
    disable_buttons()
    state.status_label.config(text=f"正在准备检查更新{status_suffix}...")
    update_log(f"⏳ 开始检查 {check_scope_message} 的更新...")
    
    session_cache = {}
    state.checking_updates_thread = threading.Thread(
        target=_check_for_updates_threaded,
        args=(packages_to_check, session_cache, is_filtered_check),
        daemon=True
    )
    state.checking_updates_thread.start()


def _check_for_updates_threaded(packages_to_check, session_cache, is_filtered_check):
    """工作线程函数，从提供的列表中查找过时包。"""
    outdated_list = []
    total_packages = len(packages_to_check)
    start_time = time.time()
    status_suffix = " (筛选后)" if is_filtered_check else ""
    
    print(f"[线程] 检查 {total_packages} 个包的更新{status_suffix}...")
    
    for i, (pkg_name, installed_version_str) in enumerate(packages_to_check):
        progress = int(((i + 1) / total_packages) * 100)
        if i % 5 == 0 or i == total_packages - 1:
            state.root.after(0, _update_progress, progress, pkg_name, total_packages, i + 1, status_suffix)
        
        latest_version_str = pip_utils.get_latest_version(pkg_name, session_cache)
        if latest_version_str:
            try:
                installed_ver = parse_version(installed_version_str)
                latest_ver = parse_version(latest_version_str)
                if latest_ver > installed_ver:
                    outdated_list.append((pkg_name, installed_version_str, latest_version_str))
            except Exception as e:
                print(f"[线程] 警告: 无法为 {pkg_name} 比较版本 ('{installed_version_str}' vs '{latest_version_str}'): {e}")
                state.root.after(0, update_log, f"⚠️ 无法比较版本: {pkg_name} ({installed_version_str} / {latest_version_str})")
    
    end_time = time.time()
    duration = end_time - start_time
    print(f"[线程] 检查在 {duration:.2f}秒内完成。找到 {len(outdated_list)} 个过时包{status_suffix}。")
    
    state.root.after(0, _updates_check_finished, outdated_list, duration, is_filtered_check)


def _update_progress(progress, current_pkg, total, count, status_suffix):
    """用进度更新状态标签（在主线程中运行）。"""
    try:
        if state.status_label and state.status_label.winfo_exists():
            state.status_label.config(text=f"正在检查更新{status_suffix} ({progress}%): {count}/{total} ({current_pkg})...")
    except tk.TclError:
        pass


def _updates_check_finished(outdated_list, duration, is_filtered_check):
    """当更新检查线程完成时调用（在主线程中运行）。"""
    state.outdated_packages_data = sorted(outdated_list)
    count = len(state.outdated_packages_data)
    checked_count_display = len(state.tree.get_children()) if is_filtered_check else len(state.all_packages)
    status_suffix = " (筛选后)" if is_filtered_check else ""
    scope_desc = f"检查了 {checked_count_display} 个显示的包" if is_filtered_check else f"检查了所有 {len(state.all_packages)} 个包"
    status_message = f"{scope_desc}，完成 ({duration:.1f}秒): 找到 {count} 个过时包{status_suffix}。"
    
    try:
        if state.status_label and state.status_label.winfo_exists():
            state.status_label.config(text=status_message)
        update_log(f"✅ {status_message}")
        enable_buttons()
        
        if count > 0:
            msg_suffix = "\n\n(注意：结果基于检查时显示的包)" if is_filtered_check else ""
            if messagebox.askyesno("检查完成", f"{status_message}{msg_suffix}\n\n是否立即切换到仅显示这些过时包的视图？"):
                if state.current_view_mode != "outdated":
                    toggle_outdated_view()
                else:
                    populate_table(view_mode="outdated")
            elif state.current_view_mode == "outdated":
                populate_table(view_mode="outdated")
        else:
            messagebox.showinfo("检查完成", f"在检查的包中未找到过时版本{status_suffix}。")
            if state.current_view_mode == "outdated":
                toggle_outdated_view()
    except tk.TclError:
        print("检查完成后更新 GUI 出错 (控件可能已被销毁)。")


def toggle_outdated_view():
    """在 'all' 和 'outdated' 之间切换表格视图。"""
    if state.outdated_packages_data is None:
        messagebox.showinfo("请先检查", "请先点击 '检查更新' 来获取过时包列表。\n(检查将基于当前视图)")
        return
    
    try:
        if state.current_view_mode == "all":
            if not state.outdated_packages_data:
                messagebox.showinfo("无过时数据", "上次检查未发现过时的包，或检查结果已被刷新。")
                if state.toggle_view_button and state.toggle_view_button.winfo_exists():
                    state.toggle_view_button.config(text="仅显示过时包", state="disabled")
                if state.update_all_button and state.update_all_button.winfo_exists():
                    state.update_all_button.config(state="disabled")
                return
            
            state.current_view_mode = "outdated"
            if state.status_label and state.status_label.winfo_exists():
                state.status_label.config(text=f"当前显示: 上次检查发现的过时包 ({len(state.outdated_packages_data)} 个)")
            populate_table(view_mode="outdated")
        else:
            state.current_view_mode = "all"
            if state.status_label and state.status_label.winfo_exists():
                state.status_label.config(text=f"当前显示: 所有包 ({len(state.all_packages)} 个)")
            populate_table(view_mode="all")
    except tk.TclError:
        print("切换视图出错 (控件可能已被销毁)。")

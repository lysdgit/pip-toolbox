import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import pkg_resources
import subprocess
import threading
import shutil
import os
from packaging.version import parse as parse_version  # 用于可靠的版本比较
import time  # 用于状态更新
import sys  # 在 __main__ 中用于平台检查

# --- 配置 ---
PIP_COMMAND = shutil.which("pip3") or shutil.which("pip") or "pip"

# --- 全局变量 ---
all_packages = []
version_comboboxes = {}
outdated_packages_data = None  # 存储 [(name, installed_ver, latest_ver)] - 反映最后一次检查
current_view_mode = "all"  # "all" 或 "outdated"
checking_updates_thread = None  # 用于管理检查线程
global_version_cache = {}  # 全局版本缓存，键为包名，值为 (版本列表, 时间戳)
update_all_button = None  # 全部更新按钮的全局引用

# --- 辅助函数 ---
def get_installed_packages():
    """获取所有已安装的 pip 包及其版本。"""
    pkg_resources._initialize_master_working_set()
    return sorted([(pkg.key, pkg.version) for pkg in pkg_resources.working_set])

def get_current_source():
    """获取当前配置的 pip 索引 URL。"""
    try:
        for scope in ["global", "user"]:
            result = subprocess.run([PIP_COMMAND, "config", "get", f"{scope}.index-url"],
                                    capture_output=True, text=True, encoding="utf-8", check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        return "默认 PyPI 源"
    except Exception as e:
        print(f"获取当前源出错: {e}")
        return "无法获取"

def parse_pip_index_versions(output, pkg_name):
    """更鲁棒地解析 'pip index versions' 的输出以获取版本列表。"""
    lines = output.splitlines()
    versions_str_list = []
    for line in lines:
        if "Available versions:" in line:
            try:
                versions_part = line.split(":", 1)[1]
                versions_str_list = [v.strip() for v in versions_part.split(',') if v.strip()]
                break
            except IndexError:
                continue
    if not versions_str_list:
        potential_version_lines = []
        for line in lines:
            cleaned_line = line.replace(f"{pkg_name}", "").replace("(", "").replace(")", "").strip()
            if not cleaned_line: continue
            parts = [p.strip() for p in cleaned_line.split(',') if p.strip()]
            valid_versions_on_line = 0
            if len(parts) > 1:
                for part in parts:
                    try:
                        parse_version(part)
                        valid_versions_on_line += 1
                    except Exception:
                        pass
                if valid_versions_on_line >= len(parts) * 0.8:
                    potential_version_lines.append((valid_versions_on_line, parts))
        if potential_version_lines:
            potential_version_lines.sort(key=lambda x: x[0], reverse=True)
            versions_str_list = potential_version_lines[0][1]
    valid_versions = []
    if versions_str_list:
        for v_str in versions_str_list:
            try:
                parsed_v = parse_version(v_str)
                valid_versions.append(parsed_v)
            except Exception:
                pass
        valid_versions.sort(reverse=True)
    if not valid_versions:
        print(f"警告: 无法从输出中为 {pkg_name} 解析任何版本:\n---\n{output}\n---")
    return [str(v) for v in valid_versions]

def get_latest_version(pkg_name, session_cache):
    """为包获取最新的可用版本，使用全局缓存。"""
    if pkg_name in global_version_cache:
        versions, timestamp = global_version_cache[pkg_name]
        if time.time() - timestamp < 300:  # 5分钟有效期
            session_cache[pkg_name] = versions[0] if versions else None
            return session_cache[pkg_name]
    try:
        command = [PIP_COMMAND, "index", "versions", pkg_name]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=25,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode == 0 and result.stdout:
            available_versions = parse_pip_index_versions(result.stdout, pkg_name)
            global_version_cache[pkg_name] = (available_versions, time.time())
            session_cache[pkg_name] = available_versions[0] if available_versions else None
            return session_cache[pkg_name]
        else:
            print(f"检查 {pkg_name} 最新版本出错: {result.stderr or result.stdout or '无输出'}")
            global_version_cache[pkg_name] = ([], time.time())
            session_cache[pkg_name] = None
            return None
    except subprocess.TimeoutExpired:
        print(f"检查 {pkg_name} 最新版本超时")
        global_version_cache[pkg_name] = ([], time.time())
        session_cache[pkg_name] = None
        return None
    except Exception as e:
        print(f"检查 {pkg_name} 最新版本时异常: {e}")
        global_version_cache[pkg_name] = ([], time.time())
        session_cache[pkg_name] = None
        return None

# --- GUI 函数 ---
def populate_table(packages_to_display=None, view_mode="all"):
    """根据视图模式用包数据填充 Treeview 表格。"""
    clear_comboboxes()
    tree.delete(*tree.get_children())
    if packages_to_display is None:
        if view_mode == "outdated" and outdated_packages_data:
            packages_to_display = [(name, installed) for name, installed, latest in outdated_packages_data]
        else:
            packages_to_display = all_packages
    for pkg_name, pkg_version in packages_to_display:
        row_id = tree.insert("", "end", values=(pkg_name, pkg_version))
        version_comboboxes[row_id] = None
    count = len(packages_to_display)
    count_prefix = "过时包数量: " if view_mode == "outdated" else "包数量: "
    package_count_label.config(text=f"{count_prefix}{count}")
    if view_mode == "outdated":
        toggle_view_button.config(text="显示所有包")
        if update_all_button and update_all_button.winfo_exists():
            update_all_button.config(state="normal" if outdated_packages_data else "disabled")
    else:
        toggle_view_button.config(text="仅显示过时包")
        if update_all_button and update_all_button.winfo_exists():
            update_all_button.config(state="disabled")
    search_packages()

def clear_comboboxes():
    """销毁任何活动的版本选择组合框。"""
    for widget in list(version_comboboxes.values()):
        if widget:
            try:
                widget.destroy()
            except tk.TclError:
                pass
    version_comboboxes.clear()

def search_packages(event=None):
    """基于搜索查询过滤表格中当前显示的包。"""
    query = search_var.get().strip().lower()
    if current_view_mode == "outdated":
        base_packages_data = outdated_packages_data or []
        base_packages_list = [(name, installed) for name, installed, latest in base_packages_data]
    else:
        base_packages_list = all_packages
    if query:
        filtered_packages = [pkg for pkg in base_packages_list if query in pkg[0].lower()]
    else:
        filtered_packages = base_packages_list
    _populate_table_internal(filtered_packages, current_view_mode)

def _populate_table_internal(packages_list, view_mode):
    """内部辅助函数，用于更新表格而不更改全局视图状态。"""
    clear_comboboxes()
    tree.delete(*tree.get_children())
    for pkg_name, pkg_version in packages_list:
        row_id = tree.insert("", "end", values=(pkg_name, pkg_version))
        version_comboboxes[row_id] = None
    count = len(packages_list)
    count_prefix = "过时包数量: " if view_mode == "outdated" else "包数量: "
    search_active = search_var.get().strip() != ""
    filter_text = "(搜索中) " if search_active else ""
    package_count_label.config(text=f"{count_prefix}{filter_text}{count}")

def fetch_versions(pkg_name, combobox):
    """为包获取可用版本（由组合框使用）。"""
    if pkg_name in global_version_cache:
        versions, timestamp = global_version_cache[pkg_name]
        if time.time() - timestamp < 300:
            available_versions_str = versions
            parsed_versions = versions
        else:
            available_versions_str = []
            parsed_versions = []
    else:
        available_versions_str = []
        parsed_versions = []
    if not parsed_versions:
        try:
            command = [PIP_COMMAND, "index", "versions", pkg_name]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=35,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode != 0 or "ERROR:" in result.stderr or "Could not find" in result.stderr or "No matching index versions found" in result.stderr:
                error_msg = result.stderr.strip() or result.stdout.strip() or '未知查询错误'
                if "Could not find a version that satisfies the requirement" in error_msg or \
                   "No matching index versions found" in error_msg:
                    error_msg = "未找到可用版本"
                elif "ERROR: Exception:" in error_msg:
                    error_msg = "查询时出错 (pip内部错误)"
                available_versions_str = [f"错误: {error_msg}"]
                parsed_versions = []
            else:
                parsed_versions = parse_pip_index_versions(result.stdout, pkg_name)
                available_versions_str = parsed_versions if parsed_versions else ["未找到版本"]
            global_version_cache[pkg_name] = (parsed_versions, time.time())
        except subprocess.TimeoutExpired:
            available_versions_str = ["查询超时"]
            parsed_versions = []
            global_version_cache[pkg_name] = ([], time.time())
        except Exception as e:
            print(f"获取 {pkg_name} 版本出错: {e}")
            available_versions_str = ["查询出错"]
            parsed_versions = []
            global_version_cache[pkg_name] = ([], time.time())
    current_installed_version = next((v for p, v in all_packages if p == pkg_name), None)
    latest_known_version = next((latest for name, _, latest in outdated_packages_data if name == pkg_name), None) if outdated_packages_data else None
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

def install_selected_version():
    """安装组合框中选定的版本。"""
    selected_items = tree.selection()
    if not selected_items:
        messagebox.showwarning("未选择", "请在表格中选择一个包。")
        return
    item_id = selected_items[0]
    try:
        pkg_name, displayed_version = tree.item(item_id, "values")
    except tk.TclError:
        messagebox.showerror("错误", "无法获取所选项目的信息 (可能已删除)。")
        return
    combobox = version_comboboxes.get(item_id)
    if not combobox or not combobox.winfo_exists() or combobox.cget('state') == 'disabled':
        messagebox.showwarning("未加载版本", f"请等待 '{pkg_name}' 的版本加载或选择完成。")
        return
    selected_value = combobox.get()
    version_to_install = selected_value.split(" ")[0].strip()
    if not version_to_install or version_to_install.startswith("错误") or \
       version_to_install.startswith("查询") or version_to_install == "未找到版本":
        messagebox.showerror("无法安装", f"无法安装选定的条目: '{selected_value}'")
        return
    current_version = next((v for p, v in all_packages if p == pkg_name), None)
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
        command = [PIP_COMMAND, "install", "--upgrade", "--no-cache-dir", target_package]
        run_pip_command_threaded(command, f"{action} {target_package}")

def uninstall_selected_package():
    """卸载选定的包。"""
    selected_items = tree.selection()
    if not selected_items:
        messagebox.showwarning("未选择", "请在表格中选择要卸载的包。")
        return
    item_id = selected_items[0]
    try:
        pkg_name = tree.item(item_id, "values")[0]
    except tk.TclError:
        messagebox.showerror("错误", "无法获取所选项目的信息 (可能已删除)。")
        return
    if messagebox.askyesno("卸载确认", f"确定要卸载 {pkg_name} 吗？"):
        command = [PIP_COMMAND, "uninstall", "-y", pkg_name]
        run_pip_command_threaded(command, f"卸载 {pkg_name}")

def update_all_packages():
    """将所有过时包更新到最新版本。"""
    if not outdated_packages_data:
        messagebox.showinfo("无过时包", "当前没有过时包需要更新。")
        return
    if messagebox.askyesno("全部更新确认", f"确定要将 {len(outdated_packages_data)} 个过时包更新到最新版本吗？"):
        disable_buttons()
        update_log(f"⏳ 开始更新 {len(outdated_packages_data)} 个过时包...\n")
        thread = threading.Thread(target=update_all_packages_threaded, args=(outdated_packages_data,), daemon=True)
        thread.start()

def update_all_packages_threaded(outdated_packages):
    """在线程中批量更新所有过时包。"""
    success = True
    total = len(outdated_packages)
    for i, (pkg_name, installed_version, latest_version) in enumerate(outdated_packages):
        target_package = f"{pkg_name}=={latest_version}"
        command = [PIP_COMMAND, "install", "--upgrade", "--no-cache-dir", target_package]
        action_name = f"更新 {pkg_name} 到 {latest_version}"
        root.after(0, update_log, f"⏳ ({i+1}/{total}) {action_name}...\n   命令: {' '.join(command)}\n")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding='utf-8', errors='replace',
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            stdout, stderr = process.communicate(timeout=600)
            if process.returncode == 0:
                root.after(0, update_log, f"✅ ({i+1}/{total}) {action_name} 成功。\n--- 输出 ---\n{stdout}\n")
                if stderr:
                    root.after(0, update_log, f"--- 警告/信息 ---\n{stderr}\n")
            else:
                success = False
                root.after(0, update_log, f"❌ ({i+1}/{total}) {action_name} 失败 (Code: {process.returncode}).\n--- 输出 ---\n{stdout}\n--- 错误 ---\n{stderr}\n")
        except subprocess.TimeoutExpired:
            success = False
            root.after(0, update_log, f"⌛ ({i+1}/{total}) {action_name} 超时 (超过10分钟)。\n")
            try:
                process.kill()
                stdout, stderr = process.communicate()
                root.after(0, update_log, f"--- 最后输出 ---\n{stdout}\n--- 最后错误 ---\n{stderr}\n")
            except Exception as kill_e:
                root.after(0, update_log, f"--- 尝试终止超时进程时出错: {kill_e} ---\n")
        except Exception as e:
            success = False
            root.after(0, update_log, f"❌ ({i+1}/{total}) 执行 {action_name} 时发生意外错误: {str(e)}\n")
    root.after(0, command_finished, f"✅ 全部更新完成 ({total} 个包)。\n", success)

def run_pip_command_threaded(command, action_name):
    """在单独线程中运行 pip 命令并更新日志。"""
    disable_buttons()
    update_log(f"⏳ {action_name}...\n   命令: {' '.join(command)}\n")
    thread = threading.Thread(target=run_pip_command_sync, args=(command, action_name), daemon=True)
    thread.start()

def run_pip_command_sync(command, action_name):
    """运行 pip 命令的同步部分，在线程中执行。"""
    output_log = ""
    success = False
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding='utf-8', errors='replace',
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        stdout, stderr = process.communicate(timeout=600)
        if process.returncode == 0:
            output_log = f"✅ {action_name} 成功。\n--- 输出 ---\n{stdout}\n"
            if stderr: output_log += f"--- 警告/信息 ---\n{stderr}\n"
            success = True
        else:
            output_log = f"❌ {action_name} 失败 (Code: {process.returncode}).\n--- 输出 ---\n{stdout}\n--- 错误 ---\n{stderr}\n"
    except subprocess.TimeoutExpired:
        output_log = f"⌛ {action_name} 超时 (超过10分钟)。\n"
        try:
            process.kill()
            stdout, stderr = process.communicate()
            output_log += f"--- 最后输出 ---\n{stdout}\n--- 最后错误 ---\n{stderr}\n"
        except Exception as kill_e:
            output_log += f"--- 尝试终止超时进程时出错: {kill_e} ---\n"
    except FileNotFoundError:
        output_log = f"❌ 命令错误: 无法找到 '{command[0]}'. 请确保 pip 在 PATH 中。\n"
    except Exception as e:
        output_log = f"❌ 执行 {action_name} 时发生意外错误: {str(e)}\n"
    root.after(0, command_finished, output_log, success)

def command_finished(log_message, needs_refresh):
    """pip 命令完成后更新 GUI。"""
    update_log(log_message)
    if needs_refresh:
        update_log("🔄 正在刷新已安装包列表...\n")
        global outdated_packages_data
        outdated_packages_data = None
        try:
            if toggle_view_button and toggle_view_button.winfo_exists():
                toggle_view_button.config(state="disabled")
            if update_all_button and update_all_button.winfo_exists():
                update_all_button.config(state="disabled")
        except (tk.TclError, NameError):
            pass
        status_label.config(text="包列表已更改，请重新检查更新。")
        refresh_package_list_threaded()
    else:
        enable_buttons()
        update_log("🔴 操作未成功完成或无需刷新列表。\n")

def refresh_package_list_threaded():
    """在后台线程中获取更新的包列表。"""
    global all_packages
    try:
        pkg_resources._initialize_master_working_set()
        all_packages = get_installed_packages()
        log_msg = "✅ 包列表刷新完成。\n"
        success = True
    except Exception as e:
        log_msg = f"❌ 刷新包列表时出错: {e}\n"
        success = False
    root.after(0, update_gui_after_refresh, log_msg, success)

def update_gui_after_refresh(log_msg, success):
    """刷新后更新表格并启用按钮。"""
    update_log(log_msg)
    if success:
        global current_view_mode
        current_view_mode = "all"
        populate_table(view_mode="all")
        status_label.config(text=f"包列表已刷新 ({len(all_packages)} 个包)。")
    else:
        status_label.config(text="刷新包列表失败。")
    enable_buttons()
    try:
        if toggle_view_button and toggle_view_button.winfo_exists():
            toggle_view_button.config(state="disabled")
        if update_all_button and update_all_button.winfo_exists():
            update_all_button.config(state="disabled")
    except (tk.TclError, NameError):
        pass

def disable_buttons():
    """在操作期间禁用按钮。"""
    for btn in [install_button, uninstall_button, change_source_button, check_updates_button, toggle_view_button, update_all_button]:
        try:
            if btn and btn.winfo_exists():
                btn.config(state="disabled")
        except (tk.TclError, NameError):
            pass

def enable_buttons():
    """操作后重新启用按钮。"""
    try:
        if install_button and install_button.winfo_exists():
            install_button.config(state="normal")
        if uninstall_button and uninstall_button.winfo_exists():
            uninstall_button.config(state="normal")
        if change_source_button and change_source_button.winfo_exists():
            change_source_button.config(state="normal")
        if check_updates_button and check_updates_button.winfo_exists():
            check_updates_button.config(state="normal")
        if toggle_view_button and toggle_view_button.winfo_exists():
            toggle_view_button.config(state="normal" if outdated_packages_data else "disabled")
        if update_all_button and update_all_button.winfo_exists():
            update_all_button.config(state="normal" if current_view_mode == "outdated" and outdated_packages_data else "disabled")
    except (tk.TclError, NameError):
        pass

def update_log(message):
    """将消息追加到日志显示区域。"""
    if not log_display_area or not log_display_area.winfo_exists():
        return
    try:
        log_display_area.config(state=tk.NORMAL)
        log_display_area.insert(tk.END, message + "\n")
        log_display_area.see(tk.END)
        log_display_area.config(state=tk.DISABLED)
    except tk.TclError as e:
        print(f"更新日志出错: {e}")

def clear_log():
    """清除日志显示区域。"""
    if not log_display_area or not log_display_area.winfo_exists():
        return
    try:
        log_display_area.config(state=tk.NORMAL)
        log_display_area.delete('1.0', tk.END)
        log_display_area.config(state=tk.DISABLED)
    except tk.TclError:
        pass

def on_tree_select(event):
    """处理 Treeview 中的选择变化，放置/更新组合框。"""
    selected_items = tree.selection()
    if not selected_items:
        for widget in version_comboboxes.values():
            if widget and widget.winfo_ismapped():
                widget.place_forget()
        return
    item_id = selected_items[0]
    for row_id, widget in list(version_comboboxes.items()):
        if widget and row_id != item_id:
            try:
                if widget.winfo_exists():
                    widget.place_forget()
            except tk.TclError:
                pass
    existing_combobox = version_comboboxes.get(item_id)
    if existing_combobox and not existing_combobox.winfo_exists():
        existing_combobox = None
        version_comboboxes[item_id] = None
    try:
        if not tree.exists(item_id):
            return
        pkg_name, _ = tree.item(item_id, "values")
    except tk.TclError:
        return
    if not existing_combobox:
        combobox = ttk.Combobox(tree, state="disabled", exportselection=False)
        version_comboboxes[item_id] = combobox
    else:
        combobox = existing_combobox
    combobox.set("正在查询版本...")
    combobox.configure(state="disabled")
    root.after(10, place_combobox, item_id, combobox, pkg_name)

def place_combobox(item_id, combobox, pkg_name):
    """放置组合框并开始获取版本。"""
    try:
        if not combobox.winfo_exists():
            return
        if not tree.exists(item_id):
            return
        bbox = tree.bbox(item_id, column=1)
        if bbox:
            x, y, width, height = bbox
            combobox.place(x=x, y=y, width=width, height=height)
            threading.Thread(target=fetch_versions, args=(pkg_name, combobox), daemon=True).start()
        else:
            combobox.place_forget()
    except tk.TclError as e:
        print(f"为 {pkg_name} 放置组合框出错: {e}")
        try:
            if combobox.winfo_exists():
                combobox.place_forget()
        except tk.TclError:
            pass

def update_combobox_position(event=None):
    """当视图变化时更新活动组合框的位置。"""
    root.after_idle(_do_update_combobox_position)

def _do_update_combobox_position():
    """更新组合框位置的实际工作。"""
    selected_items = tree.selection()
    if not selected_items:
        for row_id, widget in list(version_comboboxes.items()):
            if widget and widget.winfo_ismapped():
                widget.place_forget()
        return
    item_id = selected_items[0]
    combobox = version_comboboxes.get(item_id)
    try:
        if combobox and combobox.winfo_exists():
            if not tree.exists(item_id):
                combobox.place_forget()
                if version_comboboxes.get(item_id) == combobox:
                    version_comboboxes[item_id] = None
                return
            bbox = tree.bbox(item_id, column=1)
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

def change_source():
    """允许更改 pip 索引 URL。"""
    global outdated_packages_data
    current_src = get_current_source()
    new_source = simpledialog.askstring("更改 Pip 源",
                                       f"当前源: {current_src}\n\n输入新的 PyPI 索引 URL (留空则重置):",
                                       initialvalue="https://pypi.tuna.tsinghua.edu.cn/simple")
    if new_source is None:
        return
    if not new_source.strip():
        if messagebox.askyesno("重置确认", "确定要移除自定义源设置，恢复默认吗？"):
            update_log("正在尝试移除自定义源...")
            success = False
            try:
                cmd_global = [PIP_COMMAND, "config", "unset", "global.index-url"]
                cmd_user = [PIP_COMMAND, "config", "unset", "user.index-url"]
                subprocess.run(cmd_global, capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                subprocess.run(cmd_user, capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                success = True
                messagebox.showinfo("源已重置", "已尝试移除自定义源配置。")
                update_log("✅ 源配置已尝试重置。")
            except Exception as e:
                messagebox.showerror("错误", f"移除源时出错: {e}")
                update_log(f"❌ 移除源时出错: {e}")
                success = False
            if success:
                outdated_packages_data = None
                try:
                    if toggle_view_button and toggle_view_button.winfo_exists():
                        toggle_view_button.config(state="disabled")
                    if update_all_button and update_all_button.winfo_exists():
                        update_all_button.config(state="disabled")
                except (tk.TclError, NameError):
                    pass
                status_label.config(text="源已更改，请重新检查更新。")
        return
    if not (new_source.startswith("http://") or new_source.startswith("https://")):
        messagebox.showerror("格式错误", "源地址必须以 http:// 或 https:// 开头。")
        return
    outdated_packages_data = None
    try:
        if toggle_view_button and toggle_view_button.winfo_exists():
            toggle_view_button.config(state="disabled")
        if update_all_button and update_all_button.winfo_exists():
            update_all_button.config(state="disabled")
    except (tk.TclError, NameError):
        pass
    status_label.config(text="源已更改，请重新检查更新。")
    command = [PIP_COMMAND, "config", "set", "global.index-url", new_source]
    action_name = f"设置新源为 {new_source}"
    run_pip_command_threaded(command, action_name)
    messagebox.showinfo("正在换源", f"已开始尝试将 pip 源设置为: {new_source}\n请查看下方日志了解结果。")

def toggle_log_display():
    """显示或隐藏日志显示区域。"""
    if log_visible_var.get():
        log_frame.pack(side="bottom", fill="x", padx=5, pady=(0,0), before=status_bar)
        try:
            if clear_log_button and clear_log_button.winfo_exists():
                clear_log_button.pack(in_=status_bar, side="right", padx=(0,5), pady=1)
        except (tk.TclError, NameError):
            pass
    else:
        log_frame.pack_forget()
        try:
            if clear_log_button and clear_log_button.winfo_exists():
                clear_log_button.pack_forget()
        except (tk.TclError, NameError):
            pass

# --- 过时包逻辑 ---
def check_for_updates():
    """在当前视图中启动检查过时包的过程（尊重任何活跃过滤）。"""
    global checking_updates_thread
    if checking_updates_thread and checking_updates_thread.is_alive():
        messagebox.showinfo("请稍候", "已经在检查更新了。")
        return
    packages_to_check = []
    displayed_item_ids = tree.get_children()
    if not displayed_item_ids:
        messagebox.showinfo("无包显示", "表格中当前没有显示任何包可供检查。")
        return
    for item_id in displayed_item_ids:
        try:
            pkg_name, pkg_version = tree.item(item_id, "values")
            packages_to_check.append((pkg_name, pkg_version))
        except tk.TclError:
            print(f"警告: 无法获取项 {item_id} 的值，跳过。")
            continue
    if not packages_to_check:
        messagebox.showinfo("无包", "无法获取表格中显示的包信息。")
        return
    is_filtered_check = len(packages_to_check) < len(all_packages)
    check_scope_message = f"当前视图中的 {len(packages_to_check)} 个包" if is_filtered_check else f"所有 {len(all_packages)} 个已安装包"
    status_suffix = " (筛选后)" if is_filtered_check else ""
    disable_buttons()
    status_label.config(text=f"正在准备检查更新{status_suffix}...")
    update_log(f"⏳ 开始检查 {check_scope_message} 的更新...")
    session_cache = {}
    checking_updates_thread = threading.Thread(target=check_for_updates_threaded,
                                             args=(packages_to_check, session_cache, is_filtered_check),
                                             daemon=True)
    checking_updates_thread.start()

def check_for_updates_threaded(packages_to_check, session_cache, is_filtered_check):
    """工作线程函数，从提供的列表中查找过时包。"""
    outdated_list = []
    total_packages = len(packages_to_check)
    start_time = time.time()
    status_suffix = " (筛选后)" if is_filtered_check else ""
    print(f"[线程] 检查 {total_packages} 个包的更新{status_suffix}...")
    for i, (pkg_name, installed_version_str) in enumerate(packages_to_check):
        progress = int(((i + 1) / total_packages) * 100)
        if i % 5 == 0 or i == total_packages - 1:
            root.after(0, update_progress, progress, pkg_name, total_packages, i + 1, status_suffix)
        latest_version_str = get_latest_version(pkg_name, session_cache)
        if latest_version_str:
            try:
                installed_ver = parse_version(installed_version_str)
                latest_ver = parse_version(latest_version_str)
                if latest_ver > installed_ver:
                    outdated_list.append((pkg_name, installed_version_str, latest_version_str))
            except Exception as e:
                print(f"[线程] 警告: 无法为 {pkg_name} 比较版本 ('{installed_version_str}' vs '{latest_version_str}'): {e}")
                root.after(0, update_log, f"⚠️ 无法比较版本: {pkg_name} ({installed_version_str} / {latest_version_str})")
    end_time = time.time()
    duration = end_time - start_time
    print(f"[线程] 检查在 {duration:.2f}秒内完成。找到 {len(outdated_list)} 个过时包{status_suffix}。")
    root.after(0, updates_check_finished, outdated_list, duration, is_filtered_check)

def update_progress(progress, current_pkg, total, count, status_suffix):
    """用进度更新状态标签（在主线程中运行）。"""
    try:
        if status_label and status_label.winfo_exists():
            status_label.config(text=f"正在检查更新{status_suffix} ({progress}%): {count}/{total} ({current_pkg})...")
    except tk.TclError:
        pass

def updates_check_finished(outdated_list, duration, is_filtered_check):
    """当更新检查线程完成时调用（在主线程中运行）。"""
    global outdated_packages_data, current_view_mode
    outdated_packages_data = sorted(outdated_list)
    count = len(outdated_packages_data)
    checked_count_display = len(tree.get_children()) if is_filtered_check else len(all_packages)
    status_suffix = " (筛选后)" if is_filtered_check else ""
    scope_desc = f"检查了 {checked_count_display} 个显示的包" if is_filtered_check else f"检查了所有 {len(all_packages)} 个包"
    status_message = f"{scope_desc}，完成 ({duration:.1f}秒): 找到 {count} 个过时包{status_suffix}。"
    try:
        if status_label and status_label.winfo_exists():
            status_label.config(text=status_message)
        update_log(f"✅ {status_message}")
        enable_buttons()
        if count > 0:
            msg_suffix = "\n\n(注意：结果基于检查时显示的包)" if is_filtered_check else ""
            if messagebox.askyesno("检查完成", f"{status_message}{msg_suffix}\n\n是否立即切换到仅显示这些过时包的视图？"):
                if current_view_mode != "outdated":
                    toggle_outdated_view()
                else:
                    populate_table(view_mode="outdated")
            elif current_view_mode == "outdated":
                populate_table(view_mode="outdated")
        else:
            messagebox.showinfo("检查完成", f"在检查的包中未找到过时版本{status_suffix}。")
            if current_view_mode == "outdated":
                toggle_outdated_view()
    except tk.TclError:
        print("检查完成后更新 GUI 出错 (控件可能已被销毁)。")

def toggle_outdated_view():
    """在 'all' 和 'outdated' 之间切换表格视图。"""
    global current_view_mode
    if outdated_packages_data is None:
        messagebox.showinfo("请先检查", "请先点击 '检查更新' 来获取过时包列表。\n(检查将基于当前视图)")
        return
    try:
        if current_view_mode == "all":
            if not outdated_packages_data:
                messagebox.showinfo("无过时数据", "上次检查未发现过时的包，或检查结果已被刷新。")
                if toggle_view_button and toggle_view_button.winfo_exists():
                    toggle_view_button.config(text="仅显示过时包", state="disabled")
                if update_all_button and update_all_button.winfo_exists():
                    update_all_button.config(state="disabled")
                return
            current_view_mode = "outdated"
            if status_label and status_label.winfo_exists():
                status_label.config(text=f"当前显示: 上次检查发现的过时包 ({len(outdated_packages_data)} 个)")
            populate_table(view_mode="outdated")
        else:
            current_view_mode = "all"
            if status_label and status_label.winfo_exists():
                status_label.config(text=f"当前显示: 所有包 ({len(all_packages)} 个)")
            populate_table(view_mode="all")
    except tk.TclError:
        print("切换视图出错 (控件可能已被销毁)。")

# --- 主应用程序设置 ---
root = tk.Tk()
root.title(f"Python Pip 包管理器 (Using: {os.path.basename(PIP_COMMAND)})")
root.geometry("700x750")
root.minsize(600, 500)

# --- 样式配置 (可选) ---
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

# --- 顶部框架 (搜索和计数) ---
top_frame = ttk.Frame(root, padding="10 5 10 5")
top_frame.pack(fill="x")
ttk.Label(top_frame, text="搜索包:").pack(side="left")
search_var = tk.StringVar()
search_entry = ttk.Entry(top_frame, textvariable=search_var, width=30)
search_entry.pack(side="left", fill="x", expand=True, padx=5)
search_entry.bind("<KeyRelease>", search_packages)
package_count_label = ttk.Label(top_frame, text="包数量: 0", width=20, anchor='e')
package_count_label.pack(side="right", padx=(5, 0))

# --- 中间框架 (Treeview 和滚动条) ---
tree_frame = ttk.Frame(root, padding="10 5 10 5")
tree_frame.pack(fill="both", expand=True)
columns = ("name", "version")
tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
tree.heading("name", text="包名称", anchor="w")
tree.heading("version", text="版本信息", anchor="w")
tree.column("name", width=350, stretch=tk.YES, anchor="w")
tree.column("version", width=200, stretch=tk.YES, anchor="w")
tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=tree_scrollbar.set)
tree_scrollbar.pack(side="right", fill="y")
tree.pack(side="left", fill="both", expand=True)

# --- 按钮框架 ---
button_frame = ttk.Frame(root, padding="10 5 10 10")
button_frame.pack(fill="x")
install_button = ttk.Button(button_frame, text="安装/更新选定版本", command=install_selected_version)
install_button.pack(side="left", padx=(0, 5))
uninstall_button = ttk.Button(button_frame, text="卸载选定包", command=uninstall_selected_package)
uninstall_button.pack(side="left", padx=5)
ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side="left", fill='y', padx=10, pady=2)
check_updates_button = ttk.Button(button_frame, text="检查更新", command=check_for_updates)
check_updates_button.pack(side="left", padx=5)
toggle_view_button = ttk.Button(button_frame, text="仅显示过时包", command=toggle_outdated_view, state="disabled")
toggle_view_button.pack(side="left", padx=5)
ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side="left", fill='y', padx=10, pady=2)
update_all_button = ttk.Button(button_frame, text="全部更新", command=update_all_packages, state="disabled")
update_all_button.pack(side="left", padx=5)
change_source_button = ttk.Button(button_frame, text="更改 Pip 源", command=change_source)
change_source_button.pack(side="right", padx=(5, 0))

# --- 状态栏 ---
status_bar = ttk.Frame(root, relief=tk.SUNKEN, borderwidth=1, padding=0)
status_bar.pack(side="bottom", fill="x")
status_label = ttk.Label(status_bar, text="就绪.", anchor='w', padding=(5, 2, 5, 2))
status_label.pack(side="left", fill="x", expand=True)
log_visible_var = tk.BooleanVar(value=False)
log_toggle_checkbutton = ttk.Checkbutton(status_bar, text="日志", variable=log_visible_var, command=toggle_log_display, style='Toolbutton')
log_toggle_checkbutton.pack(side="right", padx=(0, 2), pady=1)
clear_log_button = ttk.Button(status_bar, text="清空", command=clear_log, width=5, style='Toolbutton')

# --- 日志区域 (初始隐藏) ---
log_frame = ttk.Frame(root, height=150, relief=tk.GROOVE, borderwidth=1)
log_display_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, state=tk.DISABLED, relief=tk.FLAT, bd=0, font=("Consolas", 9) if os.name=='nt' else ("Monospace", 9))
log_display_area.pack(side="top", fill="both", expand=True, padx=1, pady=1)

# --- 事件绑定 ---
tree.bind("<<TreeviewSelect>>", on_tree_select)
tree.bind("<Configure>", update_combobox_position)
root.bind("<Configure>", update_combobox_position)
tree_scrollbar.bind("<B1-Motion>", lambda e: root.after(50, update_combobox_position))
root.bind_all("<MouseWheel>", lambda e: root.after(50, update_combobox_position))
tree.bind("<Up>", lambda e: root.after(50, update_combobox_position))
tree.bind("<Down>", lambda e: root.after(50, update_combobox_position))
tree.bind("<Prior>", lambda e: root.after(50, update_combobox_position))
tree.bind("<Next>", lambda e: root.after(50, update_combobox_position))

# --- 初始数据加载 ---
def initial_load():
    """加载初始包列表并填充表格。"""
    status_label.config(text="正在加载已安装的包列表...")
    update_log("正在加载已安装的包列表...")
    disable_buttons()
    refresh_package_list_threaded()

# --- 主执行 ---
def main():
    root.after(100, initial_load)
    root.mainloop()

# --- 入口点检查 ---
if __name__ == "__main__":
    try:
        from packaging.version import parse
    except ImportError:
        messagebox.showerror("缺少库", "需要 'packaging' 库来进行版本比较。\n请尝试运行: pip install packaging")
        sys.exit(1)
    try:
        proc = subprocess.run([PIP_COMMAND.split()[0], "--version"], check=True, capture_output=True, text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        print(f"使用 pip: {proc.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        messagebox.showerror("Pip 错误", f"无法执行 '{PIP_COMMAND}'。\n请确保 Python 和 pip 已正确安装并位于系统 PATH 中。\n\n错误详情: {e}")
        sys.exit(1)
    main()
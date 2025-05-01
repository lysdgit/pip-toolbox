# --- Helper Functions ---
# ... (get_installed_packages, get_current_source remain the same) ...

def parse_pip_index_versions(output, pkg_name):
    """
    Parses the output of 'pip index versions' more robustly to get a list of versions.
    """
    lines = output.splitlines()
    versions_str_list = []

    # 1. Primary Strategy: Look for the explicit header
    for line in lines:
        if "Available versions:" in line:
            try:
                versions_part = line.split(":", 1)[1]
                versions_str_list = [v.strip() for v in versions_part.split(',') if v.strip()]
                # print(f"[Parse Debug] Found 'Available versions:' line for {pkg_name}: {versions_str_list}")
                break # Found the most reliable line, stop searching
            except IndexError:
                continue # Malformed line

    # 2. Secondary Strategy: Iterate all lines if header not found
    if not versions_str_list:
        # print(f"[Parse Debug] Header not found for {pkg_name}. Iterating lines...")
        potential_version_lines = []
        for line in lines:
            # Clean the line: remove package name and parentheses if present
            cleaned_line = line.replace(f"{pkg_name}", "").replace("(", "").replace(")", "").strip()
            if not cleaned_line: continue # Skip empty lines

            parts = [p.strip() for p in cleaned_line.split(',') if p.strip()]
            valid_versions_on_line = 0
            if len(parts) > 1: # Only consider lines with multiple comma-separated parts
                for part in parts:
                    try:
                        parse_version(part) # Check if it looks like a version
                        valid_versions_on_line += 1
                    except Exception:
                        pass # Not a valid version string
                # If most parts on the line look like versions, store it
                if valid_versions_on_line >= len(parts) * 0.8: # Heuristic: 80% look like versions
                     potential_version_lines.append((valid_versions_on_line, parts))

        # Choose the line that had the most valid-looking versions
        if potential_version_lines:
            potential_version_lines.sort(key=lambda x: x[0], reverse=True) # Sort by count of valid versions
            versions_str_list = potential_version_lines[0][1] # Get the parts from the best line
            # print(f"[Parse Debug] Heuristic found versions for {pkg_name}: {versions_str_list}")


    # 3. Final Clean and Sort
    valid_versions = []
    if versions_str_list:
        for v_str in versions_str_list:
            try:
                parsed_v = parse_version(v_str)
                valid_versions.append(parsed_v)
            except Exception:
                 print(f"Info: Skipping invalid version string '{v_str}' during final parse for {pkg_name}")
                 pass
        valid_versions.sort(reverse=True) # Sort newest first

    if not valid_versions:
         print(f"Warning: Could not parse any versions for {pkg_name} from output:\n---\n{output}\n---")

    return [str(v) for v in valid_versions] # Return as strings

# ... (get_latest_version remains the same, uses the improved parse_pip_index_versions) ...

# --- Full Code ---
# (The rest of the code remains exactly the same as the previous 'complete code' answer,
#  only the parse_pip_index_versions function above is replaced.)

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import pkg_resources
import subprocess
import threading
import shutil
import os
from packaging.version import parse as parse_version # For reliable version comparison
import time # For status updates
import sys # Needed for platform check in __main__

# --- Configuration ---
PIP_COMMAND = shutil.which("pip3") or shutil.which("pip") or "pip"

# --- Helper Functions ---
def get_installed_packages():
    """Gets all installed pip packages and their versions."""
    # Clear pkg_resources cache to get the most up-to-date list
    pkg_resources._initialize_master_working_set()
    return sorted([(pkg.key, pkg.version) for pkg in pkg_resources.working_set])

def get_current_source():
    """Gets the currently configured pip index URL."""
    try:
        # Prioritize global, then user
        for scope in ["global", "user"]:
             result = subprocess.run([PIP_COMMAND, "config", "get", f"{scope}.index-url"],
                                     capture_output=True, text=True, encoding="utf-8", check=False,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
             if result.returncode == 0 and result.stdout.strip():
                 return result.stdout.strip()
        return "默认 PyPI 源"
    except Exception as e:
        print(f"Error getting current source: {e}")
        return "无法获取"

# ** Use the new parse_pip_index_versions function from above here **
# def parse_pip_index_versions(output, pkg_name): ... (insert the new version here)

def get_latest_version(pkg_name, session_cache):
    """Fetches the latest available version for a package."""
    if pkg_name in session_cache:
        return session_cache[pkg_name]

    try:
        command = [PIP_COMMAND, "index", "versions", pkg_name]
        # Add --no-cache-dir maybe? Sometimes helps with stale index info
        # command.insert(1, "--no-cache-dir")
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=25, # Slightly longer timeout
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

        # *** Debug: Print raw output ***
        # print(f"--- pip index versions {pkg_name} ---")
        # print(result.stdout)
        # print(result.stderr)
        # print("---------------------------------")
        # *** End Debug ***

        if result.returncode == 0 and result.stdout:
            available_versions = parse_pip_index_versions(result.stdout, pkg_name)
            latest = available_versions[0] if available_versions else None
            session_cache[pkg_name] = latest # Cache result
            return latest
        else:
             # Log error but don't crash the check
             print(f"Error checking latest version for {pkg_name}: {result.stderr or result.stdout or 'No output'}")
             session_cache[pkg_name] = None # Cache failure
             return None
    except subprocess.TimeoutExpired:
        print(f"Timeout checking latest version for {pkg_name}")
        session_cache[pkg_name] = None
        return None
    except Exception as e:
        print(f"Exception checking latest version for {pkg_name}: {e}")
        session_cache[pkg_name] = None
        return None


# --- GUI Functions ---
def populate_table(packages_to_display=None, view_mode="all"):
    """Fills the Treeview table with package data based on view mode."""
    clear_comboboxes()
    tree.delete(*tree.get_children())

    if packages_to_display is None:
        if view_mode == "outdated" and outdated_packages_data:
            # Data structure for outdated is [(name, installed, latest)]
             packages_to_display = [(name, installed) for name, installed, latest in outdated_packages_data]
        else: # Default to all packages
             packages_to_display = all_packages

    for pkg_name, pkg_version in packages_to_display:
        row_id = tree.insert("", "end", values=(pkg_name, pkg_version))
        version_comboboxes[row_id] = None # Placeholder

    count = len(packages_to_display)
    count_prefix = "过时包数量: " if view_mode == "outdated" else "包数量: "
    package_count_label.config(text=f"{count_prefix}{count}")

    # Update toggle button text based on current view
    if view_mode == "outdated":
        toggle_view_button.config(text="显示所有包")
    else:
        toggle_view_button.config(text="仅显示过时包")

    # Ensure search applies correctly AFTER populating for the new view
    search_packages()


def clear_comboboxes():
    """Destroys any active version selection comboboxes."""
    for widget in list(version_comboboxes.values()):
        if widget:
            try:
                widget.destroy()
            except tk.TclError:
                 pass # Widget might already be destroyed
    version_comboboxes.clear()


def search_packages(event=None):
    """Filters packages currently displayed in the table based on the search query."""
    query = search_var.get().strip().lower()

    # Determine the base list of packages based on the current view
    if current_view_mode == "outdated":
        base_packages_data = outdated_packages_data or []
        # We need (name, installed_version) tuples for filtering
        base_packages_list = [(name, installed) for name, installed, latest in base_packages_data]
    else:
        base_packages_list = all_packages

    # Apply search filter
    if query:
        filtered_packages = [
            pkg for pkg in base_packages_list if query in pkg[0].lower()
        ]
    else:
        # If query is empty, show all packages relevant to the current view
        filtered_packages = base_packages_list

    # Repopulate the table with the filtered list for the *current view*
    _populate_table_internal(filtered_packages, current_view_mode)


def _populate_table_internal(packages_list, view_mode):
    """Internal helper to update table without changing global view state."""
    clear_comboboxes() # Clear comboboxes before repopulating
    tree.delete(*tree.get_children())

    for pkg_name, pkg_version in packages_list:
        row_id = tree.insert("", "end", values=(pkg_name, pkg_version))
        version_comboboxes[row_id] = None # Placeholder

    count = len(packages_list)
    count_prefix = "过时包数量: " if view_mode == "outdated" else "包数量: "
    # Adjust label based on whether a search filter is active
    search_active = search_var.get().strip() != ""
    filter_text = "(搜索中) " if search_active else ""
    package_count_label.config(text=f"{count_prefix}{filter_text}{count}")


def fetch_versions(pkg_name, combobox):
    """Fetches available versions for a package (used by combobox)."""
    # Find current installed version from the main list
    current_installed_version = next((v for p, v in all_packages if p == pkg_name), None)
    latest_known_version = None

    # If we have outdated data, use the known latest version for comparison
    if outdated_packages_data:
        latest_known_version = next((latest for name, _, latest in outdated_packages_data if name == pkg_name), None)

    try:
        command = [PIP_COMMAND, "index", "versions", pkg_name]
        # Add --no-cache-dir maybe? Sometimes helps with stale index info
        # command.insert(1, "--no-cache-dir")
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=35, # Longer timeout
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

        # *** Debug: Print raw output ***
        # print(f"--- fetch_versions: pip index versions {pkg_name} ---")
        # print(result.stdout)
        # print(result.stderr)
        # print("------------------------------------------")
        # *** End Debug ***

        # Check for common errors first
        if result.returncode != 0 or "ERROR:" in result.stderr or "Could not find" in result.stderr or "No matching index versions found" in result.stderr:
             error_msg = result.stderr.strip() or result.stdout.strip() or '未知查询错误'
             # Specific message for common "not found" cases
             if "Could not find a version that satisfies the requirement" in error_msg or \
                "No matching index versions found" in error_msg:
                 error_msg = "未找到可用版本"
             elif "ERROR: Exception:" in error_msg: # Generic pip exception
                  error_msg = "查询时出错 (pip内部错误)"

             available_versions_str = [f"错误: {error_msg}"]
             parsed_versions = [] # Ensure this is empty on error

        else: # If no immediate error, try parsing
            parsed_versions = parse_pip_index_versions(result.stdout, pkg_name)
            if not parsed_versions:
                 # If parsing yielded nothing, but command succeeded, it's likely no versions exist
                 available_versions_str = ["未找到版本"]
            else:
                 available_versions_str = parsed_versions # Use the successfully parsed list

    except subprocess.TimeoutExpired:
        available_versions_str = ["查询超时"]
        parsed_versions = []
    except Exception as e:
        print(f"Error fetching versions for {pkg_name}: {e}")
        available_versions_str = ["查询出错"]
        parsed_versions = []

    # Prepare display list (use parsed_versions if successful, else available_versions_str)
    source_list = parsed_versions if parsed_versions else available_versions_str
    display_versions = []
    found_installed = False
    best_match_index = 0 # Default to first item

    for i, v_str in enumerate(source_list):
        label = v_str
        is_current = (v_str == current_installed_version)
        # Check latest known version only if it's valid (not None)
        is_latest = (latest_known_version is not None and v_str == latest_known_version)

        # Add labels only if it's not an error message
        if not v_str.startswith("错误:") and not v_str.startswith("查询") and not v_str.startswith("未找到"):
            if is_current:
                label += " (当前)"
                found_installed = True
                best_match_index = i # Prefer selecting current if available
            if is_latest and not is_current: # Avoid double labels
                 label += " (最新)"
                 if not found_installed: # If current wasn't found, select latest
                     best_match_index = i

        display_versions.append(label)

    # Ensure combobox still exists before configuring
    try:
        if combobox.winfo_exists():
            combobox.configure(state="readonly")
            combobox["values"] = display_versions

            if display_versions:
                combobox.set(display_versions[best_match_index])
            else:
                # Should ideally not happen if error handling above works
                combobox.set("无可用版本")
    except tk.TclError:
        print(f"Info: Combobox for {pkg_name} was destroyed before versions could be set.")


def install_selected_version():
    """Installs the version selected in the combobox."""
    selected_items = tree.selection()
    if not selected_items:
        messagebox.showwarning("未选择", "请在表格中选择一个包。")
        return

    item_id = selected_items[0]
    try:
        pkg_name, displayed_version = tree.item(item_id, "values") # This is the installed version
    except tk.TclError:
        messagebox.showerror("错误", "无法获取所选项目的信息 (可能已删除)。")
        return

    combobox = version_comboboxes.get(item_id)
    if not combobox or not combobox.winfo_exists() or combobox.cget('state') == 'disabled':
        messagebox.showwarning("未加载版本", f"请等待 '{pkg_name}' 的版本加载或选择完成。")
        return

    selected_value = combobox.get()
    # Extract the actual version number (remove labels like "(当前)", "(最新)")
    version_to_install = selected_value.split(" ")[0].strip()

    if not version_to_install or version_to_install.startswith("错误") or \
       version_to_install.startswith("查询") or version_to_install == "未找到版本":
        messagebox.showerror("无法安装", f"无法安装选定的条目: '{selected_value}'")
        return

    # Find the actual current installed version from the master list
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
             print(f"Warning: Could not parse versions for comparison: {e}. Using default prompt.")
             action = "安装/更改" # Generic action if comparison fails
             prompt = f"确定要安装/更改到 {pkg_name}=={version_to_install} 吗？"


    if messagebox.askyesno(f"{action}确认", prompt):
        target_package = f"{pkg_name}=={version_to_install}"
        # Use --upgrade flag for installs/updates/downgrades, it handles all cases
        # Add --no-cache-dir to potentially avoid issues with corrupted caches
        command = [PIP_COMMAND, "install", "--upgrade", "--no-cache-dir", target_package]
        run_pip_command_threaded(command, f"{action} {target_package}")


def uninstall_selected_package():
    """Uninstalls the selected package."""
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


def run_pip_command_threaded(command, action_name):
    """Runs a pip command in a separate thread and updates the log."""
    disable_buttons()
    update_log(f"⏳ {action_name}...\n   命令: {' '.join(command)}\n")
    thread = threading.Thread(target=run_pip_command_sync, args=(command, action_name), daemon=True)
    thread.start()

def run_pip_command_sync(command, action_name):
    """Synchronous part of running pip command, executed in a thread."""
    output_log = ""
    success = False
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8', errors='replace',
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        stdout, stderr = process.communicate(timeout=600) # Increased timeout to 10 minutes

        if process.returncode == 0:
            output_log = f"✅ {action_name} 成功。\n--- 输出 ---\n{stdout}\n"
            # Also include stderr for warnings even on success
            if stderr: output_log += f"--- 警告/信息 ---\n{stderr}\n"
            success = True
        else:
            output_log = f"❌ {action_name} 失败 (Code: {process.returncode}).\n--- 输出 ---\n{stdout}\n--- 错误 ---\n{stderr}\n"

    except subprocess.TimeoutExpired:
        output_log = f"⌛ {action_name} 超时 (超过10分钟)。\n"
        try:
            process.kill() # Terminate the timed-out process
            stdout, stderr = process.communicate() # Capture any final output
            output_log += f"--- 最后输出 ---\n{stdout}\n--- 最后错误 ---\n{stderr}\n"
        except Exception as kill_e:
             output_log += f"--- 尝试终止超时进程时出错: {kill_e} ---\n"
    except FileNotFoundError:
         output_log = f"❌ 命令错误: 无法找到 '{command[0]}'. 请确保 pip 在 PATH 中。\n"
    except Exception as e:
        output_log = f"❌ 执行 {action_name} 时发生意外错误: {str(e)}\n"

    # Ensure GUI updates happen on the main thread
    root.after(0, command_finished, output_log, success)


def command_finished(log_message, needs_refresh):
    """Updates GUI after pip command finishes."""
    # Declare global at the top of the function that modifies it
    global outdated_packages_data

    update_log(log_message)
    if needs_refresh:
        update_log("🔄 正在刷新已安装包列表...\n")
        # Invalidate outdated cache as list has changed
        outdated_packages_data = None # Assignment happens *after* global declaration
        # Disable toggle button immediately as data is invalid
        try: # Protect against errors if button doesn't exist yet
            if toggle_view_button and toggle_view_button.winfo_exists():
                toggle_view_button.config(state="disabled")
        except (tk.TclError, NameError): pass
        status_label.config(text="包列表已更改，请重新检查更新。")
        refresh_package_list_threaded() # This will re-enable buttons when done
    else:
        enable_buttons() # Re-enable buttons if no refresh was triggered
        update_log("🔴 操作未成功完成或无需刷新列表。\n")


def refresh_package_list_threaded():
    """Fetches the updated package list in a background thread."""
    global all_packages
    try:
        # Ensure pkg_resources cache is not stale
        pkg_resources._initialize_master_working_set()
        all_packages = get_installed_packages()
        log_msg = "✅ 包列表刷新完成。\n"
        success = True
    except Exception as e:
        log_msg = f"❌ 刷新包列表时出错: {e}\n"
        success = False
    root.after(0, update_gui_after_refresh, log_msg, success)

def update_gui_after_refresh(log_msg, success):
     """Updates the table and enables buttons after refresh."""
     update_log(log_msg)
     if success:
        # Reset view to "all" and repopulate
        global current_view_mode
        current_view_mode = "all"
        populate_table(view_mode="all") # This calls search_packages internally
        status_label.config(text=f"包列表已刷新 ({len(all_packages)} 个包)。")
     else:
         status_label.config(text="刷新包列表失败。")
     enable_buttons()
     # Toggle button state depends on whether outdated data *was* available
     # Since we invalidated it, it should start disabled until next check
     try:
         if toggle_view_button and toggle_view_button.winfo_exists():
            toggle_view_button.config(state="disabled")
     except (tk.TclError, NameError): pass


def disable_buttons():
    """Disables buttons during operations."""
    for btn in [install_button, uninstall_button, change_source_button, check_updates_button, toggle_view_button]:
        try:
            if btn and btn.winfo_exists(): # Check if widget exists
                btn.config(state="disabled")
        except (tk.TclError, NameError): pass # Ignore if widget destroyed or not defined yet

def enable_buttons():
    """Re-enables buttons after operations."""
    try:
        if install_button and install_button.winfo_exists(): install_button.config(state="normal")
        if uninstall_button and uninstall_button.winfo_exists(): uninstall_button.config(state="normal")
        if change_source_button and change_source_button.winfo_exists(): change_source_button.config(state="normal")
        if check_updates_button and check_updates_button.winfo_exists(): check_updates_button.config(state="normal")
        if toggle_view_button and toggle_view_button.winfo_exists():
            # Only enable toggle if outdated data is available and valid
            toggle_view_button.config(state="normal" if outdated_packages_data else "disabled")
    except (tk.TclError, NameError): pass # Ignore if widget destroyed or not defined yet


def update_log(message):
    """Appends a message to the log display area."""
    if not log_display_area or not log_display_area.winfo_exists(): return
    try:
        log_display_area.config(state=tk.NORMAL)
        log_display_area.insert(tk.END, message + "\n")
        log_display_area.see(tk.END)
        log_display_area.config(state=tk.DISABLED)
    except tk.TclError as e:
        print(f"Error updating log: {e}") # Handle cases where widget might be destroyed during update

def clear_log():
    """Clears the log display area."""
    if not log_display_area or not log_display_area.winfo_exists(): return
    try:
        log_display_area.config(state=tk.NORMAL)
        log_display_area.delete('1.0', tk.END)
        log_display_area.config(state=tk.DISABLED)
    except tk.TclError:
        pass # Ignore if widget destroyed

def on_tree_select(event):
    """Handles selection changes in the Treeview, placing/updating combobox."""
    # Allow processing to continue only if the event happened on the treeview itself
    # (Prevents errors if event triggered by combobox gaining focus internally)
    # if event.widget != tree:
    #     return

    selected_items = tree.selection()
    if not selected_items:
        # Clear potentially visible combobox if selection is lost
        for widget in version_comboboxes.values():
            if widget and widget.winfo_ismapped():
                widget.place_forget()
        return

    item_id = selected_items[0]

    # Forget any combobox not for the current selection
    for row_id, widget in list(version_comboboxes.items()):
        if widget and row_id != item_id:
            try: # Check if widget exists before trying to place_forget
                if widget.winfo_exists():
                    widget.place_forget()
            except tk.TclError: pass # Widget might be gone

    existing_combobox = version_comboboxes.get(item_id)
    # Ensure existing combobox hasn't been destroyed
    if existing_combobox and not existing_combobox.winfo_exists():
        existing_combobox = None
        version_comboboxes[item_id] = None # Clear stale reference

    # Check if already placed *and* visible
    if existing_combobox and existing_combobox.winfo_ismapped():
        # Maybe just update position if needed, handled by update_combobox_position
        return

    try:
        # Ensure item still exists before proceeding
        if not tree.exists(item_id): return
        pkg_name, _ = tree.item(item_id, "values")
    except tk.TclError:
        return # Item might have been deleted

    if not existing_combobox:
        # Create combobox within the treeview for proper placement
        combobox = ttk.Combobox(tree, state="disabled", exportselection=False)
        version_comboboxes[item_id] = combobox
    else:
        combobox = existing_combobox

    combobox.set("正在查询版本...")
    combobox.configure(state="disabled") # Ensure disabled while fetching

    # Defer placement slightly to allow treeview layout to settle
    root.after(10, place_combobox, item_id, combobox, pkg_name)

def place_combobox(item_id, combobox, pkg_name):
    """Places the combobox and starts fetching versions."""
    try:
        if not combobox.winfo_exists(): return # Check again if destroyed

        # Ensure the item still exists in the tree
        if not tree.exists(item_id): return

        bbox = tree.bbox(item_id, column=1) # Bbox for the "Version" column

        if bbox:
            x, y, width, height = bbox
            # Adjust placement slightly if needed (e.g., center vertically)
            # y_offset = (height - combobox.winfo_reqheight()) // 2
            # combobox.place(x=x, y=y + y_offset, width=width, height=combobox.winfo_reqheight())
            combobox.place(x=x, y=y, width=width, height=height) # Use full cell height

            # Start fetching versions in background thread
            threading.Thread(target=fetch_versions, args=(pkg_name, combobox), daemon=True).start()
        else:
            # Item might not be visible (scrolled away), don't place
            combobox.place_forget()

    except tk.TclError as e:
        print(f"Error placing combobox for {pkg_name}: {e}")
        try: # Try to hide it if placement failed but widget exists
            if combobox.winfo_exists():
                combobox.place_forget()
        except tk.TclError: pass


def update_combobox_position(event=None):
    """Updates the position of the active combobox when view changes."""
    # Use after idle to ensure layout calculations are complete
    root.after_idle(_do_update_combobox_position)

def _do_update_combobox_position():
    """The actual work of updating combobox position."""
    selected_items = tree.selection()
    if not selected_items:
        # If nothing is selected, ensure no combobox is visible
        for row_id, widget in list(version_comboboxes.items()):
             if widget and widget.winfo_ismapped():
                 widget.place_forget()
        return

    item_id = selected_items[0]
    combobox = version_comboboxes.get(item_id)

    try:
        if combobox and combobox.winfo_exists():
            # Ensure the item still exists
            if not tree.exists(item_id):
                 combobox.place_forget()
                 if version_comboboxes.get(item_id) == combobox:
                     version_comboboxes[item_id] = None # Clear reference if item gone
                 return

            bbox = tree.bbox(item_id, column=1)
            if bbox:
                x, y, width, height = bbox
                # Only replace if necessary
                current_info = combobox.place_info()
                # Compare as strings for simplicity with tk results
                if (str(x) != current_info.get('x') or
                    str(y) != current_info.get('y') or
                    str(width) != current_info.get('width') or
                    str(height) != current_info.get('height')):
                    # combobox.place(x=x, y=y + y_offset, width=width, height=combobox.winfo_reqheight())
                    combobox.place(x=x, y=y, width=width, height=height) # Use full cell height
            else:
                # Item scrolled out of view, hide the combobox
                combobox.place_forget()
    except tk.TclError:
        pass # Ignore errors if widgets are destroyed during update

def change_source():
    """Allows changing the pip index URL."""
    # Declare global at the top of the function that modifies it
    global outdated_packages_data

    current_src = get_current_source()
    new_source = simpledialog.askstring("更改 Pip 源",
                                        f"当前源: {current_src}\n\n输入新的 PyPI 索引 URL (留空则重置):",
                                        initialvalue="https://pypi.tuna.tsinghua.edu.cn/simple")

    if new_source is None: return # User cancelled

    if not new_source.strip():
         if messagebox.askyesno("重置确认", "确定要移除自定义源设置，恢复默认吗？"):
             update_log("正在尝试移除自定义源...")
             success = False
             try:
                 # Try unsetting both global and user scopes, pip handles non-existent keys gracefully
                 cmd_global = [PIP_COMMAND, "config", "unset", "global.index-url"]
                 cmd_user = [PIP_COMMAND, "config", "unset", "user.index-url"]
                 # Run commands without checking return code strictly, as key might not exist
                 subprocess.run(cmd_global, capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                 subprocess.run(cmd_user, capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                 # Assume success unless exception occurs during run
                 success = True
                 messagebox.showinfo("源已重置", "已尝试移除自定义源配置。")
                 update_log("✅ 源配置已尝试重置。")

             except Exception as e:
                  messagebox.showerror("错误", f"移除源时出错: {e}")
                  update_log(f"❌ 移除源时出错: {e}")
                  success = False

             if success:
                  # Invalidate outdated cache as source change affects availability
                  outdated_packages_data = None # Assignment happens *after* global declaration
                  try:
                      if toggle_view_button and toggle_view_button.winfo_exists():
                         toggle_view_button.config(state="disabled")
                  except (tk.TclError, NameError): pass
                  status_label.config(text="源已更改，请重新检查更新。")
         return

    if not (new_source.startswith("http://") or new_source.startswith("https://")):
        messagebox.showerror("格式错误", "源地址必须以 http:// 或 https:// 开头。")
        return

    # Try setting globally first
    command = [PIP_COMMAND, "config", "set", "global.index-url", new_source]
    action_name = f"设置新源为 {new_source}"

    # Invalidate outdated cache after changing source
    outdated_packages_data = None # Assignment happens *after* global declaration
    try:
        if toggle_view_button and toggle_view_button.winfo_exists():
            toggle_view_button.config(state="disabled")
    except (tk.TclError, NameError): pass
    status_label.config(text="源已更改，请重新检查更新。")

    run_pip_command_threaded(command, action_name)
    # Show immediate feedback, final status will be in log
    messagebox.showinfo("正在换源", f"已开始尝试将 pip 源设置为: {new_source}\n请查看下方日志了解结果。")


def toggle_log_display():
    """Shows or hides the log display area."""
    if log_visible_var.get():
        # Pack log frame itself
        log_frame.pack(side="bottom", fill="x", padx=5, pady=(0,0), before=status_bar) # Pack before status bar
        # Pack clear button into the status bar
        try: # Ensure clear_log_button exists
            if clear_log_button and clear_log_button.winfo_exists():
                clear_log_button.pack(in_=status_bar, side="right", padx=(0,5), pady=1) # Pack inside status bar
        except (tk.TclError, NameError): pass
    else:
        log_frame.pack_forget()
        try: # Ensure clear_log_button exists
            if clear_log_button and clear_log_button.winfo_exists():
                clear_log_button.pack_forget() # Hide clear button
        except (tk.TclError, NameError): pass

# --- Outdated Packages Logic ---

outdated_packages_data = None # Stores [(name, installed_ver, latest_ver)] - reflects the LAST check performed
current_view_mode = "all" # "all" or "outdated"
checking_updates_thread = None # To manage the check thread

def check_for_updates():
    """
    Starts the process of checking for outdated packages IN THE CURRENT VIEW
    (respecting any active filter).
    """
    global checking_updates_thread
    if checking_updates_thread and checking_updates_thread.is_alive():
        messagebox.showinfo("请稍候", "已经在检查更新了。")
        return

    # Get packages currently displayed in the treeview
    packages_to_check = []
    displayed_item_ids = tree.get_children()
    if not displayed_item_ids:
         messagebox.showinfo("无包显示", "表格中当前没有显示任何包可供检查。")
         return # Don't start check if nothing is displayed

    for item_id in displayed_item_ids:
        try:
            pkg_name, pkg_version = tree.item(item_id, "values")
            packages_to_check.append((pkg_name, pkg_version))
        except tk.TclError:
            print(f"Warning: Could not get values for item {item_id}, skipping.")
            continue # Skip if item somehow invalid

    if not packages_to_check: # Double-check after potential errors
         messagebox.showinfo("无包", "无法获取表格中显示的包信息。")
         return

    is_filtered_check = len(packages_to_check) < len(all_packages)
    check_scope_message = f"当前视图中的 {len(packages_to_check)} 个包" if is_filtered_check else f"所有 {len(all_packages)} 个已安装包"
    status_suffix = " (筛选后)" if is_filtered_check else ""

    disable_buttons()
    status_label.config(text=f"正在准备检查更新{status_suffix}...")
    update_log(f"⏳ 开始检查 {check_scope_message} 的更新...")


    # Create a thread-safe cache for this check session
    session_cache = {}
    checking_updates_thread = threading.Thread(target=check_for_updates_threaded,
                                               args=(packages_to_check, session_cache, is_filtered_check), # Pass filtered flag
                                               daemon=True)
    checking_updates_thread.start()

def check_for_updates_threaded(packages_to_check, session_cache, is_filtered_check):
    """
    Worker thread function to find outdated packages from the provided list.
    Receives `is_filtered_check` flag for logging/status purposes only.
    """
    # This function runs in a background thread
    # DO NOT use global outdated_packages_data here for assignment
    outdated_list = [] # Local list for results
    total_packages = len(packages_to_check)
    start_time = time.time()
    status_suffix = " (筛选后)" if is_filtered_check else ""
    print(f"[Thread] Checking updates for {total_packages} packages{status_suffix}...")

    for i, (pkg_name, installed_version_str) in enumerate(packages_to_check):
        # Update progress (schedule GUI update in main thread)
        progress = int(((i + 1) / total_packages) * 100)
        # Throttle GUI updates slightly
        if i % 5 == 0 or i == total_packages - 1:
             # Pass the status suffix to the progress updater
             root.after(0, update_progress, progress, pkg_name, total_packages, i + 1, status_suffix)

        latest_version_str = get_latest_version(pkg_name, session_cache)

        if latest_version_str:
            try:
                installed_ver = parse_version(installed_version_str)
                latest_ver = parse_version(latest_version_str)
                if latest_ver > installed_ver:
                    outdated_list.append((pkg_name, installed_version_str, latest_version_str))
            except Exception as e:
                print(f"[Thread] Warning: Could not compare versions for {pkg_name} ('{installed_version_str}' vs '{latest_version_str}'): {e}")
                root.after(0, update_log, f"⚠️ 无法比较版本: {pkg_name} ({installed_version_str} / {latest_version_str})")

    # Update GUI after check completes (schedule in main thread)
    end_time = time.time()
    duration = end_time - start_time
    print(f"[Thread] Check finished in {duration:.2f}s. Found {len(outdated_list)} outdated packages{status_suffix}.")
    root.after(0, updates_check_finished, outdated_list, duration, is_filtered_check) # Pass filtered flag back


def update_progress(progress, current_pkg, total, count, status_suffix):
    """Updates the status label with progress (runs in main thread)."""
    try:
        if status_label and status_label.winfo_exists():
            status_label.config(text=f"正在检查更新{status_suffix} ({progress}%): {count}/{total} ({current_pkg})...")
    except tk.TclError:
        pass

def updates_check_finished(outdated_list, duration, is_filtered_check):
    """
    Called when the update check thread finishes (runs in main thread).
    Updates the global outdated data based on the results of THIS check.
    """
    # Declare global at the top of the function where assignment happens
    global outdated_packages_data, current_view_mode

    # Overwrite global data with the results of this specific check
    outdated_packages_data = sorted(outdated_list)
    count = len(outdated_packages_data)

    status_suffix = " (筛选后)" if is_filtered_check else ""
    # Get the count of items actually *displayed* when the check started
    checked_count_display = 0
    try: # Protect against errors if tree items change during check
        # Use len(tree.get_children()) to get the count at the time the check finished
        checked_count_display = len(tree.get_children()) if is_filtered_check else len(all_packages)
    except Exception as e:
        print(f"Error getting tree children count: {e}")
        checked_count_display = '未知数量' # Fallback text

    scope_desc = f"检查了 {checked_count_display} 个显示的包" if is_filtered_check else f"检查了所有 {len(all_packages)} 个包"
    status_message = f"{scope_desc}，完成 ({duration:.1f}秒): 找到 {count} 个过时包{status_suffix}。"

    try:
        if status_label and status_label.winfo_exists():
            status_label.config(text=status_message)
        update_log(f"✅ {status_message}")
        enable_buttons() # Re-enable buttons

        if count > 0:
            msg_suffix = "\n\n(注意：结果基于检查时显示的包)" if is_filtered_check else ""
            if messagebox.askyesno("检查完成", f"{status_message}{msg_suffix}\n\n是否立即切换到仅显示这些过时包的视图？"):
                 # Ensure we are not already in outdated view before switching unnecessarily
                 if current_view_mode != "outdated":
                     toggle_outdated_view()
                 else:
                     # If already in outdated view, just refresh it with the new data
                     populate_table(view_mode="outdated")

            # If user says no, but we are in outdated view, refresh it anyway to reflect current check results
            elif current_view_mode == "outdated":
                 populate_table(view_mode="outdated")

        else: # No outdated packages found in the checked set
             messagebox.showinfo("检查完成", f"在检查的包中未找到过时版本{status_suffix}。")
             # If we are currently in the outdated view, switch back to all, as the outdated list for this check is empty
             if current_view_mode == "outdated":
                 toggle_outdated_view() # This will switch to 'all'
             # enable_buttons already handled disabling the toggle if count is 0

    except tk.TclError:
        print("Error updating GUI after check finished (widgets might be destroyed).")


def toggle_outdated_view():
    """
    Switches the table view between 'all' and 'outdated'.
    The 'outdated' view shows data from the *last completed check*.
    """
    global current_view_mode

    # Check if data exists from a previous check
    if outdated_packages_data is None:
         messagebox.showinfo("请先检查", "请先点击 '检查更新' 来获取过时包列表。\n(检查将基于当前视图)")
         return

    try:
        if current_view_mode == "all":
            # Check if the last check actually found any outdated packages
            if not outdated_packages_data:
                 messagebox.showinfo("无过时数据", "上次检查未发现过时的包，或检查结果已被刷新。")
                 if toggle_view_button and toggle_view_button.winfo_exists():
                     toggle_view_button.config(text="仅显示过时包", state="disabled")
                 return
            current_view_mode = "outdated"
            if status_label and status_label.winfo_exists():
                status_label.config(text=f"当前显示: 上次检查发现的过时包 ({len(outdated_packages_data)} 个)")
            populate_table(view_mode="outdated") # This populates and calls search
        else: # Currently showing outdated, switch back to all
            current_view_mode = "all"
            if status_label and status_label.winfo_exists():
                status_label.config(text=f"当前显示: 所有包 ({len(all_packages)} 个)")
            populate_table(view_mode="all") # This populates and calls search
    except tk.TclError:
         print("Error toggling view (widgets might be destroyed).")


# --- Main Application Setup ---
root = tk.Tk()
root.title(f"Python Pip 包管理器 (Using: {os.path.basename(PIP_COMMAND)})")
root.geometry("700x750")
root.minsize(600, 500)

# --- Style Configuration (Optional) ---
style = ttk.Style()
# Attempt to use a theme that generally looks better across platforms
try:
    # Windows: 'vista', 'xpnative'
    # MacOS: 'aqua'
    # Linux: 'clam', 'alt', 'default'
    if os.name == 'nt':
        style.theme_use('vista')
    elif sys.platform == 'darwin': # Check for macOS specifically
        style.theme_use('aqua')
    else:
        style.theme_use('clam') # A reasonable default for Linux
except tk.TclError:
     print("Note: Selected ttk theme not available, using default.")

style.configure('Toolbutton', font=('Segoe UI', 9) if os.name == 'nt' else ('Sans', 9)) # Smaller font

# --- Top Frame (Search and Count) ---
top_frame = ttk.Frame(root, padding="10 5 10 5") # Use ttk frame and padding
top_frame.pack(fill="x")

ttk.Label(top_frame, text="搜索包:").pack(side="left")
search_var = tk.StringVar()
search_entry = ttk.Entry(top_frame, textvariable=search_var, width=30)
search_entry.pack(side="left", fill="x", expand=True, padx=5)
search_entry.bind("<KeyRelease>", search_packages)

package_count_label = ttk.Label(top_frame, text="包数量: 0", width=20, anchor='e') # Use ttk label, increased width
package_count_label.pack(side="right", padx=(5, 0))


# --- Middle Frame (Treeview and Scrollbar) ---
tree_frame = ttk.Frame(root, padding="10 5 10 5")
tree_frame.pack(fill="both", expand=True)

columns = ("name", "version")
tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
tree.heading("name", text="包名称", anchor="w")
tree.heading("version", text="版本信息", anchor="w")
tree.column("name", width=350, stretch=tk.YES, anchor="w") # Anchor text left
tree.column("version", width=200, stretch=tk.YES, anchor="w")

tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=tree_scrollbar.set)

tree_scrollbar.pack(side="right", fill="y")
tree.pack(side="left", fill="both", expand=True)

# --- Button Frame ---
button_frame = ttk.Frame(root, padding="10 5 10 10")
button_frame.pack(fill="x")

install_button = ttk.Button(button_frame, text="安装/更新选定版本", command=install_selected_version)
install_button.pack(side="left", padx=(0, 5))

uninstall_button = ttk.Button(button_frame, text="卸载选定包", command=uninstall_selected_package)
uninstall_button.pack(side="left", padx=5)

# Separator for visual grouping
ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side="left", fill='y', padx=10, pady=2)

check_updates_button = ttk.Button(button_frame, text="检查更新", command=check_for_updates)
check_updates_button.pack(side="left", padx=5)

toggle_view_button = ttk.Button(button_frame, text="仅显示过时包", command=toggle_outdated_view, state="disabled")
toggle_view_button.pack(side="left", padx=5)


change_source_button = ttk.Button(button_frame, text="更改 Pip 源", command=change_source)
change_source_button.pack(side="right", padx=(5, 0))


# --- Status Bar ---
status_bar = ttk.Frame(root, relief=tk.SUNKEN, borderwidth=1, padding=0)
status_bar.pack(side="bottom", fill="x")

status_label = ttk.Label(status_bar, text="就绪.", anchor='w', padding=(5, 2, 5, 2))
status_label.pack(side="left", fill="x", expand=True)

log_visible_var = tk.BooleanVar(value=False)
log_toggle_checkbutton = ttk.Checkbutton(status_bar, text="日志", variable=log_visible_var, command=toggle_log_display, style='Toolbutton')
log_toggle_checkbutton.pack(side="right", padx=(0, 2), pady=1)

clear_log_button = ttk.Button(status_bar, text="清空", command=clear_log, width=5, style='Toolbutton')
# Clear log button packed/unpacked in toggle_log_display


# --- Log Area (Initially Hidden) ---
# Use a Ttk Frame for consistency if desired, though standard Frame is fine
log_frame = ttk.Frame(root, height=150, relief=tk.GROOVE, borderwidth=1)
# Don't pack log_frame here

log_display_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, state=tk.DISABLED, relief=tk.FLAT, bd=0, font=("Consolas", 9) if os.name=='nt' else ("Monospace", 9)) # Monospaced font
log_display_area.pack(side="top", fill="both", expand=True, padx=1, pady=1)


# --- Global Data Initialization ---
all_packages = []
version_comboboxes = {} # Dictionary to map row_id to combobox widget

# --- Event Bindings ---
tree.bind("<<TreeviewSelect>>", on_tree_select)
# Update position on resize/scroll
tree.bind("<Configure>", update_combobox_position)
root.bind("<Configure>", update_combobox_position)
tree_scrollbar.bind("<B1-Motion>", lambda e: root.after(50, update_combobox_position))
# Use bind_all for mousewheel to catch it even if focus isn't on tree/scrollbar
root.bind_all("<MouseWheel>", lambda e: root.after(50, update_combobox_position))
# Also update on vertical scroll using keys
tree.bind("<Up>", lambda e: root.after(50, update_combobox_position))
tree.bind("<Down>", lambda e: root.after(50, update_combobox_position))
tree.bind("<Prior>", lambda e: root.after(50, update_combobox_position)) # PageUp
tree.bind("<Next>", lambda e: root.after(50, update_combobox_position)) # PageDown


# --- Initial Data Load ---
def initial_load():
    """Loads initial package list and populates the table."""
    status_label.config(text="正在加载已安装的包列表...")
    update_log("正在加载已安装的包列表...")
    disable_buttons() # Disable until list loaded
    refresh_package_list_threaded() # Load async

# --- Main Execution ---
def main():
    # Perform initial load shortly after GUI starts
    root.after(100, initial_load)
    root.mainloop()

# --- Entry Point Check ---
if __name__ == "__main__":
    # Check for required 'packaging' library first
    try:
        from packaging.version import parse
    except ImportError:
        messagebox.showerror("缺少库", "需要 'packaging' 库来进行版本比较。\n请尝试运行: pip install packaging")
        sys.exit(1)

    # Basic check for pip command existence
    try:
        # Use --version for a quick check that doesn't need internet
        proc = subprocess.run([PIP_COMMAND.split()[0], "--version"], check=True, capture_output=True, text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        print(f"Using pip: {proc.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
         messagebox.showerror("Pip 错误", f"无法执行 '{PIP_COMMAND}'.\n请确保 Python 和 pip 已正确安装并位于系统 PATH 中。\n\n错误详情: {e}")
         # Exit if pip is not found, as the app is unusable
         sys.exit(1)

    main()
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog  # 导入 simpledialog 模块
import pkg_resources
import subprocess
import threading
import shutil

# 自动检测可用的 pip 命令
PIP_COMMAND = shutil.which("pip") or shutil.which("pip3") or "pip"

def get_installed_packages():
    """获取所有已安装的 pip 库及其版本"""
    return sorted([(pkg.key, pkg.version) for pkg in pkg_resources.working_set])

def populate_table(packages=None):
    """填充表格数据"""
    tree.delete(*tree.get_children())  # 清空表格数据
    packages = packages or all_packages  # 若无筛选条件，则显示所有包

    for pkg_name, pkg_version in packages:
        row_id = tree.insert("", "end", values=(pkg_name, pkg_version))
        version_comboboxes[row_id] = None  # 存储 combobox
    
    # 更新包数量显示
    package_count_label.config(text=f"包数量: {len(packages)}")

def search_packages(event=None):
    """根据搜索框的输入筛选包"""
    query = search_var.get().strip().lower()
    filtered_packages = [pkg for pkg in all_packages if query in pkg[0].lower()] if query else all_packages
    populate_table(filtered_packages)

def fetch_versions(pkg_name, combobox):
    """查询 pip 源获取指定库的可用版本"""
    try:
        result = subprocess.run([PIP_COMMAND, "index", "versions", pkg_name], capture_output=True, text=True, encoding="utf-8")
        output = result.stdout
        versions = []
        for line in output.splitlines():
            if "Available versions:" in line:
                versions = line.split(":")[1].strip().split(", ")
                break
        versions = versions or ["获取失败"]
    except Exception:
        versions = ["错误"]
    
    # 获取当前安装的版本
    installed_version = next((pkg_version for pkg_name2, pkg_version in all_packages if pkg_name2 == pkg_name), None)
    
    # 更新 combobox
    combobox["values"] = versions
    combobox.set(versions[0] if versions else "获取失败")
    
    # 标记当前安装的版本
    if installed_version and installed_version in versions:
        combobox["values"] = [f"{v} (已安装)" if v == installed_version else v for v in versions]

def install_selected_version():
    """安装用户选择的版本"""
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("提示", "请选择要安装的包")
        return

    item = selected_item[0]
    values = tree.item(item, "values")
    pkg_name = values[0]
    
    combobox = version_comboboxes.get(item)
    if not combobox:
        messagebox.showwarning("提示", "请先点击包名以加载版本")
        return

    selected_version = combobox.get()
    if not selected_version or selected_version in ["获取失败", "错误"]:
        messagebox.showwarning("提示", "无法安装此版本")
        return

    confirm = messagebox.askyesno("安装确认", f"是否安装 {pkg_name}=={selected_version}？")
    if confirm:
        install_button["state"] = "disabled"
        uninstall_button["state"] = "disabled"
        log_text.set(f"正在安装 {pkg_name}=={selected_version}...")
        threading.Thread(target=run_pip_command, args=([PIP_COMMAND, "install", f"{pkg_name}=={selected_version}"], f"安装 {pkg_name}=={selected_version}"), daemon=True).start()

def uninstall_selected_package():
    """卸载用户选择的包"""
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("提示", "请选择要卸载的包")
        return

    item = selected_item[0]
    values = tree.item(item, "values")
    pkg_name = values[0]

    confirm = messagebox.askyesno("卸载确认", f"是否卸载 {pkg_name}？")
    if confirm:
        install_button["state"] = "disabled"
        uninstall_button["state"] = "disabled"
        log_text.set(f"正在卸载 {pkg_name}...")
        threading.Thread(target=run_pip_command, args=([PIP_COMMAND, "uninstall", "-y", pkg_name], f"卸载 {pkg_name}"), daemon=True).start()

def run_pip_command(command, action_name):
    """执行 pip 命令（安装/卸载）"""
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True)
        log_text.set(result.stdout)
    except subprocess.CalledProcessError as e:
        log_text.set(f"错误: {e.stderr}")
    finally:
        install_button["state"] = "normal"
        uninstall_button["state"] = "normal"
        
        # 刷新已安装库列表
        global all_packages
        all_packages = get_installed_packages()
        populate_table()

def on_tree_select(event):
    """当用户选择某行时，第二列变为下拉框，并查询可用版本"""
    selected_item = tree.selection()
    if not selected_item:
        return

    # 清除先前存在的下拉框
    for item in version_comboboxes.values():
        if item is not None:
            item.place_forget()

    for item in selected_item:
        values = tree.item(item, "values")
        pkg_name, current_version = values

        # 避免重复创建 combobox
        if item in version_comboboxes and version_comboboxes[item]:
            return

        # 创建一个下拉框，父容器改为 root
        combobox = ttk.Combobox(root, state="readonly")
        combobox.set("查询中...")
        version_comboboxes[item] = combobox

        # 计算单元格的绝对位置
        x, y, width, height = tree.bbox(item, column=1)
        # 转换为相对于窗口的坐标
        abs_x = tree.winfo_rootx() + x
        abs_y = tree.winfo_rooty() + y
        combobox.place(x=abs_x, y=abs_y, width=width, height=height)

        # 启动线程查询可用版本
        threading.Thread(target=fetch_versions, args=(pkg_name, combobox), daemon=True).start()

# 创建主窗口
root = tk.Tk()
root.title("Python Pip 包管理器")
root.geometry("500x600")

# 搜索框
search_frame = tk.Frame(root)
search_frame.pack(fill="x", padx=10, pady=5)
tk.Label(search_frame, text="搜索库:").pack(side="left")
search_var = tk.StringVar()
search_entry = tk.Entry(search_frame, textvariable=search_var)
search_entry.pack(side="left", fill="x", expand=True, padx=5)
search_entry.bind("<KeyRelease>", search_packages)

# 新增：显示当前包数量的标签
package_count_label = tk.Label(search_frame, text="包数量: 0")
package_count_label.pack(side="right", padx=10)

# 创建表格
columns = ("名称", "版本")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("名称", text="名称", anchor="w")
tree.heading("版本", text="版本", anchor="w")
tree.column("名称", width=250)
tree.column("版本", width=100)

# 添加滚动条
scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)

# 绑定选择事件
tree.bind("<<TreeviewSelect>>", on_tree_select)

# 按钮区
button_frame = tk.Frame(root)
button_frame.pack(fill="x", pady=5)
install_button = tk.Button(button_frame, text="安装选定版本", command=install_selected_version)
install_button.pack(side="left", padx=10)
uninstall_button = tk.Button(button_frame, text="卸载选定库", command=uninstall_selected_package)
uninstall_button.pack(side="right", padx=10)

# 新增：换源按钮
def change_source():
    current_source = get_current_source()
    response = messagebox.askyesno("换源", f"当前源: {current_source}\n是否需要换源？")
    if response:
        new_source = simpledialog.askstring("换源", "请输入新的源地址:")  # 使用 simpledialog 获取新的源地址
        if new_source:
            try:
                subprocess.run([PIP_COMMAND, "config", "set", "global.index-url", new_source], check=True)
                messagebox.showinfo("提示", "换源成功")
            except subprocess.CalledProcessError:
                messagebox.showerror("错误", "换源失败")

change_source_button = tk.Button(button_frame, text="换源", command=change_source)
change_source_button.pack(side="right", padx=10)

# 日志显示
log_text = tk.StringVar()
log_label = tk.Label(root, textvariable=log_text, fg="blue", wraplength=480, justify="left")
log_label.pack(fill="x", padx=10, pady=5)

# 布局
tree.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# 获取所有安装的 pip 库
all_packages = get_installed_packages()
version_comboboxes = {}  # 存储下拉框数据
populate_table()

# 新增：获取当前源的函数
def get_current_source():
    try:
        result = subprocess.run([PIP_COMMAND, "config", "get", "global.index-url"], capture_output=True, text=True, encoding="utf-8", check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "默认源"

# 新增：主函数
def main():
    root.mainloop()

# 调用主函数
if __name__ == "__main__":
    main()


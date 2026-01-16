"""
Python Pip 包管理器 - PyQt5 版本
现代化的 GUI 界面，用于管理 Python 包
"""

import sys
import os
import re
import time
import shutil
import subprocess
import threading
from typing import Optional, List, Tuple, Dict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QLabel, QComboBox, QTextEdit, QMessageBox,
    QInputDialog, QProgressBar, QFrame, QSplitter, QCheckBox,
    QAbstractItemView, QStyle, QStyleFactory
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon

import pkg_resources
from packaging.version import parse as parse_version

# --- 配置 ---
# 使用 python -m pip 方式调用，更可靠
PIP_COMMAND_LIST = [sys.executable, "-m", "pip"]

# --- 全局缓存 ---
global_version_cache: Dict[str, Tuple[List[str], float]] = {}

# --- 样式表 ---
STYLE_SHEET = """
QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}

QLabel {
    color: #cdd6f4;
    padding: 2px;
}

QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #89b4fa;
    padding: 10px;
}

QLabel#statusLabel {
    color: #a6adc8;
    padding: 5px 10px;
    background-color: #181825;
    border-radius: 4px;
}

QLabel#countLabel {
    color: #94e2d5;
    font-weight: bold;
}

QLineEdit {
    background-color: #313244;
    border: 2px solid #45475a;
    border-radius: 8px;
    padding: 8px 12px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
}

QLineEdit:focus {
    border-color: #89b4fa;
}

QLineEdit::placeholder {
    color: #6c7086;
}

QPushButton {
    background-color: #45475a;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    color: #cdd6f4;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #585b70;
}

QPushButton:pressed {
    background-color: #313244;
}

QPushButton:disabled {
    background-color: #313244;
    color: #6c7086;
}

QPushButton#primaryButton {
    background-color: #89b4fa;
    color: #1e1e2e;
}

QPushButton#primaryButton:hover {
    background-color: #b4befe;
}

QPushButton#primaryButton:pressed {
    background-color: #74c7ec;
}

QPushButton#dangerButton {
    background-color: #f38ba8;
    color: #1e1e2e;
}

QPushButton#dangerButton:hover {
    background-color: #eba0ac;
}

QPushButton#successButton {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

QPushButton#successButton:hover {
    background-color: #94e2d5;
}

QPushButton#warningButton {
    background-color: #fab387;
    color: #1e1e2e;
}

QPushButton#warningButton:hover {
    background-color: #f9e2af;
}

QTableWidget {
    background-color: #181825;
    border: 2px solid #313244;
    border-radius: 10px;
    gridline-color: #313244;
    selection-background-color: #45475a;
}

QTableWidget::item {
    padding: 10px;
    border-bottom: 1px solid #313244;
}

QTableWidget::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}

QTableWidget::item:hover {
    background-color: #313244;
}

QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    font-weight: bold;
    padding: 12px;
    border: none;
    border-bottom: 2px solid #45475a;
}

QScrollBar:vertical {
    background-color: #181825;
    width: 12px;
    border-radius: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #181825;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QComboBox {
    background-color: #313244;
    border: 2px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    min-width: 150px;
}

QComboBox:hover {
    border-color: #585b70;
}

QComboBox:focus {
    border-color: #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #cdd6f4;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    border: 2px solid #45475a;
    border-radius: 6px;
    selection-background-color: #45475a;
    color: #cdd6f4;
}

QTextEdit {
    background-color: #181825;
    border: 2px solid #313244;
    border-radius: 8px;
    padding: 8px;
    color: #a6adc8;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}

QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 6px;
}

QCheckBox {
    color: #cdd6f4;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #45475a;
    border-radius: 4px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QCheckBox::indicator:hover {
    border-color: #585b70;
}

QFrame#separator {
    background-color: #45475a;
    max-height: 2px;
    margin: 10px 0;
}

QSplitter::handle {
    background-color: #45475a;
}

QSplitter::handle:hover {
    background-color: #585b70;
}
"""


# --- 辅助函数 ---
def get_installed_packages() -> List[Tuple[str, str]]:
    """获取所有已安装的 pip 包及其版本。"""
    pkg_resources._initialize_master_working_set()
    return sorted([(pkg.key, pkg.version) for pkg in pkg_resources.working_set])


def get_current_source() -> str:
    """获取当前配置的 pip 索引 URL。"""
    try:
        for scope in ["global", "user"]:
            result = subprocess.run(
                PIP_COMMAND_LIST + ["config", "get", f"{scope}.index-url"],
                capture_output=True, text=True, encoding="utf-8", check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        return "默认 PyPI 源"
    except Exception as e:
        print(f"获取当前源出错: {e}")
        return "无法获取"


def list_rc_versions(package_name: str) -> List[str]:
    """获取包的 RC 版本。"""
    try:
        result = subprocess.run(
            PIP_COMMAND_LIST + ["install", f"{package_name}==0.0.89rc1", "--pre"],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        m = re.search(r"from versions: (.+?)\)", result.stderr, re.DOTALL)
        if not m:
            return []
        versions = [v.strip() for v in m.group(1).split(",")]
        return [v for v in versions if "rc" in v.lower()]
    except Exception:
        return []


def parse_pip_index_versions(output: str, pkg_name: str) -> List[str]:
    """解析 'pip index versions' 的输出以获取版本列表。"""
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
        for line in lines:
            cleaned_line = line.replace(f"{pkg_name}", "").replace("(", "").replace(")", "").strip()
            if not cleaned_line:
                continue
            parts = [p.strip() for p in cleaned_line.split(',') if p.strip()]
            if len(parts) > 1:
                valid_count = sum(1 for p in parts if _is_valid_version(p))
                if valid_count >= len(parts) * 0.8:
                    versions_str_list = parts
                    break
    
    valid_versions = []
    for v_str in versions_str_list:
        if _is_valid_version(v_str):
            valid_versions.append(parse_version(v_str))
    
    # 添加 RC 版本
    for rc_v in list_rc_versions(pkg_name):
        if _is_valid_version(rc_v):
            valid_versions.append(parse_version(rc_v))
    
    valid_versions.sort(reverse=True)
    return [str(v) for v in valid_versions]


def _is_valid_version(v: str) -> bool:
    """检查版本字符串是否有效。"""
    try:
        parse_version(v)
        return True
    except Exception:
        return False


def get_latest_version(pkg_name: str) -> Optional[str]:
    """获取包的最新版本。"""
    if pkg_name in global_version_cache:
        versions, timestamp = global_version_cache[pkg_name]
        if time.time() - timestamp < 300:  # 5分钟缓存
            return versions[0] if versions else None
    
    try:
        command = PIP_COMMAND_LIST + ["index", "versions", pkg_name]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", timeout=25,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0 and result.stdout:
            versions = parse_pip_index_versions(result.stdout, pkg_name)
            global_version_cache[pkg_name] = (versions, time.time())
            return versions[0] if versions else None
        else:
            global_version_cache[pkg_name] = ([], time.time())
            return None
    except Exception as e:
        print(f"获取 {pkg_name} 最新版本出错: {e}")
        global_version_cache[pkg_name] = ([], time.time())
        return None


# --- 工作线程 ---
class PackageLoaderThread(QThread):
    """加载包列表的线程。"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def run(self):
        try:
            packages = get_installed_packages()
            self.finished.emit(packages)
        except Exception as e:
            self.error.emit(str(e))


class UpdateCheckerThread(QThread):
    """检查更新的线程。"""
    progress = pyqtSignal(int, str, int, int)
    finished = pyqtSignal(list, float)
    error = pyqtSignal(str)
    
    def __init__(self, packages: List[Tuple[str, str]]):
        super().__init__()
        self.packages = packages
    
    def run(self):
        outdated = []
        total = len(self.packages)
        start_time = time.time()
        
        for i, (name, installed_ver) in enumerate(self.packages):
            self.progress.emit(int((i + 1) / total * 100), name, i + 1, total)
            latest_ver = get_latest_version(name)
            if latest_ver:
                try:
                    if parse_version(latest_ver) > parse_version(installed_ver):
                        outdated.append((name, installed_ver, latest_ver))
                except Exception:
                    pass
        
        duration = time.time() - start_time
        self.finished.emit(outdated, duration)


class VersionFetcherThread(QThread):
    """获取包版本的线程。"""
    finished = pyqtSignal(str, list)
    
    def __init__(self, pkg_name: str):
        super().__init__()
        self.pkg_name = pkg_name
    
    def run(self):
        if self.pkg_name in global_version_cache:
            versions, timestamp = global_version_cache[self.pkg_name]
            if time.time() - timestamp < 300:
                self.finished.emit(self.pkg_name, versions)
                return
        
        try:
            command = PIP_COMMAND_LIST + ["index", "versions", self.pkg_name]
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8", timeout=35,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0 and result.stdout:
                versions = parse_pip_index_versions(result.stdout, self.pkg_name)
                global_version_cache[self.pkg_name] = (versions, time.time())
                self.finished.emit(self.pkg_name, versions)
            else:
                self.finished.emit(self.pkg_name, [])
        except Exception as e:
            print(f"获取 {self.pkg_name} 版本出错: {e}")
            self.finished.emit(self.pkg_name, [])


class PipCommandThread(QThread):
    """执行 pip 命令的线程。"""
    output = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, command: List[str], action_name: str):
        super().__init__()
        self.command = command
        self.action_name = action_name
    
    def run(self):
        self.output.emit(f"⏳ {self.action_name}...\n   命令: {' '.join(self.command)}\n")
        
        try:
            process = subprocess.Popen(
                self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout, stderr = process.communicate(timeout=600)
            
            if process.returncode == 0:
                msg = f"✅ {self.action_name} 成功。\n--- 输出 ---\n{stdout}\n"
                if stderr:
                    msg += f"--- 警告/信息 ---\n{stderr}\n"
                self.output.emit(msg)
                self.finished.emit(True, self.action_name)
            else:
                msg = f"❌ {self.action_name} 失败 (Code: {process.returncode}).\n--- 输出 ---\n{stdout}\n--- 错误 ---\n{stderr}\n"
                self.output.emit(msg)
                self.finished.emit(False, self.action_name)
        except subprocess.TimeoutExpired:
            self.output.emit(f"⌛ {self.action_name} 超时 (超过10分钟)。\n")
            self.finished.emit(False, self.action_name)
        except Exception as e:
            self.output.emit(f"❌ 执行 {self.action_name} 时发生错误: {str(e)}\n")
            self.finished.emit(False, self.action_name)


class BatchUpdateThread(QThread):
    """批量更新包的线程。"""
    output = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool)
    
    def __init__(self, packages: List[Tuple[str, str, str]]):
        super().__init__()
        self.packages = packages
    
    def run(self):
        total = len(self.packages)
        all_success = True
        
        for i, (name, installed, latest) in enumerate(self.packages):
            self.progress.emit(i + 1, total)
            target = f"{name}=={latest}"
            command = PIP_COMMAND_LIST + ["install", "--upgrade", "--no-cache-dir", target]
            action = f"更新 {name} 到 {latest}"
            
            self.output.emit(f"⏳ ({i+1}/{total}) {action}...\n   命令: {' '.join(command)}\n")
            
            try:
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                stdout, stderr = process.communicate(timeout=600)
                
                if process.returncode == 0:
                    self.output.emit(f"✅ ({i+1}/{total}) {action} 成功。\n")
                else:
                    all_success = False
                    self.output.emit(f"❌ ({i+1}/{total}) {action} 失败。\n--- 错误 ---\n{stderr}\n")
            except Exception as e:
                all_success = False
                self.output.emit(f"❌ ({i+1}/{total}) {action} 出错: {e}\n")
        
        self.finished.emit(all_success)


# --- 主窗口 ---
class PipToolboxWindow(QMainWindow):
    """Pip 包管理器主窗口。"""
    
    def __init__(self):
        super().__init__()
        self.all_packages: List[Tuple[str, str]] = []
        self.outdated_packages: List[Tuple[str, str, str]] = []
        self.current_view = "all"  # "all" 或 "outdated"
        self.active_threads: List[QThread] = []
        self.version_fetcher: Optional[VersionFetcherThread] = None
        
        self.init_ui()
        self.load_packages()
    
    def init_ui(self):
        """初始化用户界面。"""
        self.setWindowTitle("Python Pip 包管理器 (PyQt5)")
        
        # 设置窗口大小
        screen = QApplication.primaryScreen().geometry()
        width = int(screen.width() * 0.5)
        height = int(screen.height() * 0.75)
        self.setGeometry(200, 100, width, height)
        self.setMinimumSize(800, 600)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🐍 Python Pip 包管理器")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 当前源显示
        source_label = QLabel(f"📦 源: {get_current_source()[:50]}...")
        source_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        title_layout.addWidget(source_label)
        main_layout.addLayout(title_layout)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 搜索包:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入包名称进行搜索...")
        self.search_input.textChanged.connect(self.filter_packages)
        self.package_count_label = QLabel("包数量: 0")
        self.package_count_label.setObjectName("countLabel")
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.package_count_label)
        main_layout.addLayout(search_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 包列表表格
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["包名称", "当前版本", "可用版本"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        
        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)
        
        # 日志区域
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        log_header = QHBoxLayout()
        log_title = QLabel("📋 操作日志")
        log_title.setStyleSheet("font-weight: bold; color: #89b4fa;")
        self.clear_log_btn = QPushButton("清空")
        self.clear_log_btn.setFixedWidth(60)
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(self.clear_log_btn)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        
        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_container)
        
        splitter.setSizes([500, 150])
        main_layout.addWidget(splitter, 1)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        main_layout.addWidget(self.progress_bar)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 左侧按钮
        self.install_btn = QPushButton("📥 安装/更新")
        self.install_btn.setObjectName("primaryButton")
        self.install_btn.clicked.connect(self.install_selected)
        
        self.uninstall_btn = QPushButton("🗑️ 卸载")
        self.uninstall_btn.setObjectName("dangerButton")
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        
        button_layout.addWidget(self.install_btn)
        button_layout.addWidget(self.uninstall_btn)
        
        # 分隔
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setStyleSheet("background-color: #45475a;")
        button_layout.addWidget(separator1)
        
        # 更新相关按钮
        self.check_updates_btn = QPushButton("🔄 检查更新")
        self.check_updates_btn.clicked.connect(self.check_updates)
        
        self.toggle_view_btn = QPushButton("📋 仅显示过时包")
        self.toggle_view_btn.clicked.connect(self.toggle_view)
        self.toggle_view_btn.setEnabled(False)
        
        self.update_all_btn = QPushButton("⬆️ 全部更新")
        self.update_all_btn.setObjectName("successButton")
        self.update_all_btn.clicked.connect(self.update_all)
        self.update_all_btn.setEnabled(False)
        
        button_layout.addWidget(self.check_updates_btn)
        button_layout.addWidget(self.toggle_view_btn)
        button_layout.addWidget(self.update_all_btn)
        
        button_layout.addStretch()
        
        # 右侧按钮
        self.change_source_btn = QPushButton("⚙️ 更改源")
        self.change_source_btn.setObjectName("warningButton")
        self.change_source_btn.clicked.connect(self.change_source)
        
        self.refresh_btn = QPushButton("🔃 刷新")
        self.refresh_btn.clicked.connect(self.load_packages)
        
        button_layout.addWidget(self.change_source_btn)
        button_layout.addWidget(self.refresh_btn)
        
        main_layout.addLayout(button_layout)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusLabel")
        main_layout.addWidget(self.status_label)
    
    def log(self, message: str):
        """添加日志消息。"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def clear_log(self):
        """清空日志。"""
        self.log_text.clear()
    
    def set_buttons_enabled(self, enabled: bool):
        """设置按钮启用状态。"""
        self.install_btn.setEnabled(enabled)
        self.uninstall_btn.setEnabled(enabled)
        self.check_updates_btn.setEnabled(enabled)
        self.change_source_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        if enabled:
            self.toggle_view_btn.setEnabled(len(self.outdated_packages) > 0)
            self.update_all_btn.setEnabled(
                self.current_view == "outdated" and len(self.outdated_packages) > 0
            )
        else:
            self.toggle_view_btn.setEnabled(False)
            self.update_all_btn.setEnabled(False)
    
    def load_packages(self):
        """加载已安装的包列表。"""
        self.set_buttons_enabled(False)
        self.status_label.setText("正在加载包列表...")
        self.log("🔄 正在加载已安装的包列表...\n")
        
        self.loader_thread = PackageLoaderThread()
        self.loader_thread.finished.connect(self.on_packages_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()
        self.active_threads.append(self.loader_thread)
    
    def on_packages_loaded(self, packages: List[Tuple[str, str]]):
        """包加载完成回调。"""
        self.all_packages = packages
        self.outdated_packages = []
        self.current_view = "all"
        self.populate_table(packages)
        self.status_label.setText(f"已加载 {len(packages)} 个包")
        self.log(f"✅ 成功加载 {len(packages)} 个已安装包\n")
        self.set_buttons_enabled(True)
        self.toggle_view_btn.setEnabled(False)
        self.update_all_btn.setEnabled(False)
    
    def on_load_error(self, error: str):
        """加载错误回调。"""
        self.status_label.setText("加载失败")
        self.log(f"❌ 加载包列表失败: {error}\n")
        self.set_buttons_enabled(True)
        QMessageBox.critical(self, "错误", f"加载包列表失败:\n{error}")
    
    def populate_table(self, packages: List[Tuple[str, str]]):
        """填充表格数据。"""
        self.table.setRowCount(0)
        self.table.setRowCount(len(packages))
        
        for row, (name, version) in enumerate(packages):
            # 包名
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            
            # 当前版本
            version_item = QTableWidgetItem(version)
            version_item.setFlags(version_item.flags() & ~Qt.ItemIsEditable)
            
            # 检查是否过时
            if self.current_view == "outdated":
                for pkg_name, installed, latest in self.outdated_packages:
                    if pkg_name == name:
                        version_item.setForeground(QColor("#f38ba8"))
                        break
            
            self.table.setItem(row, 1, version_item)
            
            # 版本选择下拉框
            combo = QComboBox()
            combo.addItem("点击选择加载...")
            combo.setEnabled(False)
            self.table.setCellWidget(row, 2, combo)
        
        count_text = f"过时包: {len(packages)}" if self.current_view == "outdated" else f"包数量: {len(packages)}"
        self.package_count_label.setText(count_text)
    
    def filter_packages(self):
        """根据搜索框过滤包列表。"""
        query = self.search_input.text().strip().lower()
        
        if self.current_view == "outdated":
            base_packages = [(n, i) for n, i, l in self.outdated_packages]
        else:
            base_packages = self.all_packages
        
        if query:
            filtered = [(n, v) for n, v in base_packages if query in n.lower()]
        else:
            filtered = base_packages
        
        self.populate_table(filtered)
    
    def on_selection_changed(self):
        """选中行变化时加载版本。"""
        selected = self.table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        
        pkg_name = name_item.text()
        combo = self.table.cellWidget(row, 2)
        
        if combo and combo.count() <= 1:
            combo.clear()
            combo.addItem("正在加载版本...")
            
            self.version_fetcher = VersionFetcherThread(pkg_name)
            self.version_fetcher.finished.connect(
                lambda name, versions: self.on_versions_fetched(row, name, versions)
            )
            self.version_fetcher.start()
    
    def on_versions_fetched(self, row: int, pkg_name: str, versions: List[str]):
        """版本获取完成回调。"""
        if row >= self.table.rowCount():
            return
        
        combo = self.table.cellWidget(row, 2)
        if not combo:
            return
        
        combo.clear()
        
        if not versions:
            combo.addItem("无可用版本")
            combo.setEnabled(False)
            return
        
        # 获取当前安装版本
        current_ver = None
        name_item = self.table.item(row, 0)
        if name_item:
            for n, v in self.all_packages:
                if n == name_item.text():
                    current_ver = v
                    break
        
        # 填充版本列表
        for ver in versions:
            label = ver
            if ver == current_ver:
                label += " (当前)"
            combo.addItem(label)
        
        combo.setEnabled(True)
        
        # 选中当前版本
        if current_ver:
            for i in range(combo.count()):
                if combo.itemText(i).startswith(current_ver):
                    combo.setCurrentIndex(i)
                    break
    
    def install_selected(self):
        """安装选定版本。"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "未选择", "请先选择一个包")
            return
        
        row = selected[0].row()
        name_item = self.table.item(row, 0)
        combo = self.table.cellWidget(row, 2)
        
        if not name_item or not combo or not combo.isEnabled():
            QMessageBox.warning(self, "无法安装", "请等待版本加载完成")
            return
        
        pkg_name = name_item.text()
        selected_ver = combo.currentText().split(" ")[0].strip()
        
        if not selected_ver or selected_ver in ["无可用版本", "正在加载版本..."]:
            QMessageBox.warning(self, "无法安装", "请选择有效的版本")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认安装",
            f"确定要安装 {pkg_name}=={selected_ver} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            target = f"{pkg_name}=={selected_ver}"
            command = PIP_COMMAND_LIST + ["install", "--upgrade", "--no-cache-dir", target]
            self.run_pip_command(command, f"安装 {target}")
    
    def uninstall_selected(self):
        """卸载选定的包。"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "未选择", "请先选择一个包")
            return
        
        row = selected[0].row()
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        
        pkg_name = name_item.text()
        
        reply = QMessageBox.question(
            self, "确认卸载",
            f"确定要卸载 {pkg_name} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            command = PIP_COMMAND_LIST + ["uninstall", "-y", pkg_name]
            self.run_pip_command(command, f"卸载 {pkg_name}")
    
    def run_pip_command(self, command: List[str], action_name: str):
        """执行 pip 命令。"""
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 无限进度
        
        self.command_thread = PipCommandThread(command, action_name)
        self.command_thread.output.connect(self.log)
        self.command_thread.finished.connect(self.on_command_finished)
        self.command_thread.start()
        self.active_threads.append(self.command_thread)
    
    def on_command_finished(self, success: bool, action_name: str):
        """命令执行完成回调。"""
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText(f"{action_name} 完成")
            # 刷新包列表
            self.load_packages()
        else:
            self.status_label.setText(f"{action_name} 失败")
            self.set_buttons_enabled(True)
    
    def check_updates(self):
        """检查更新。"""
        # 获取当前显示的包
        packages = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            ver_item = self.table.item(row, 1)
            if name_item and ver_item:
                packages.append((name_item.text(), ver_item.text()))
        
        if not packages:
            QMessageBox.warning(self, "无包", "没有可检查的包")
            return
        
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.status_label.setText("正在检查更新...")
        self.log(f"🔄 开始检查 {len(packages)} 个包的更新...\n")
        
        self.update_checker = UpdateCheckerThread(packages)
        self.update_checker.progress.connect(self.on_update_check_progress)
        self.update_checker.finished.connect(self.on_update_check_finished)
        self.update_checker.start()
        self.active_threads.append(self.update_checker)
    
    def on_update_check_progress(self, percent: int, pkg_name: str, current: int, total: int):
        """更新检查进度回调。"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"检查更新 ({percent}%): {current}/{total} - {pkg_name}")
    
    def on_update_check_finished(self, outdated: List[Tuple[str, str, str]], duration: float):
        """更新检查完成回调。"""
        self.progress_bar.setVisible(False)
        self.outdated_packages = sorted(outdated)
        count = len(outdated)
        
        self.status_label.setText(f"检查完成: 找到 {count} 个过时包 (用时 {duration:.1f}s)")
        self.log(f"✅ 检查完成: 找到 {count} 个过时包\n")
        
        if count > 0:
            for name, installed, latest in outdated:
                self.log(f"   📦 {name}: {installed} → {latest}\n")
        
        self.set_buttons_enabled(True)
        self.toggle_view_btn.setEnabled(count > 0)
        
        if count > 0:
            reply = QMessageBox.question(
                self, "检查完成",
                f"找到 {count} 个过时包。\n是否切换到仅显示过时包视图？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.toggle_view()
    
    def toggle_view(self):
        """切换视图模式。"""
        if self.current_view == "all":
            if not self.outdated_packages:
                QMessageBox.information(self, "无过时包", "没有过时的包可显示")
                return
            self.current_view = "outdated"
            packages = [(n, i) for n, i, l in self.outdated_packages]
            self.toggle_view_btn.setText("📋 显示所有包")
            self.update_all_btn.setEnabled(True)
            self.status_label.setText(f"显示 {len(packages)} 个过时包")
        else:
            self.current_view = "all"
            packages = self.all_packages
            self.toggle_view_btn.setText("📋 仅显示过时包")
            self.update_all_btn.setEnabled(False)
            self.status_label.setText(f"显示所有 {len(packages)} 个包")
        
        self.search_input.clear()
        self.populate_table(packages)
    
    def update_all(self):
        """更新所有过时包。"""
        if not self.outdated_packages:
            QMessageBox.information(self, "无过时包", "没有需要更新的包")
            return
        
        count = len(self.outdated_packages)
        reply = QMessageBox.question(
            self, "确认更新",
            f"确定要更新 {count} 个过时包到最新版本吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, count)
        self.log(f"⏳ 开始批量更新 {count} 个包...\n")
        
        self.batch_thread = BatchUpdateThread(self.outdated_packages)
        self.batch_thread.output.connect(self.log)
        self.batch_thread.progress.connect(lambda c, t: self.progress_bar.setValue(c))
        self.batch_thread.finished.connect(self.on_batch_update_finished)
        self.batch_thread.start()
        self.active_threads.append(self.batch_thread)
    
    def on_batch_update_finished(self, success: bool):
        """批量更新完成回调。"""
        self.progress_bar.setVisible(False)
        self.log(f"{'✅' if success else '⚠️'} 批量更新完成\n")
        self.status_label.setText("批量更新完成")
        self.load_packages()
    
    def change_source(self):
        """更改 pip 源。"""
        current = get_current_source()
        
        new_source, ok = QInputDialog.getText(
            self, "更改 Pip 源",
            f"当前源: {current}\n\n输入新的 PyPI 索引 URL (留空则重置):",
            text="https://pypi.tuna.tsinghua.edu.cn/simple"
        )
        
        if not ok:
            return
        
        if not new_source.strip():
            # 重置源
            reply = QMessageBox.question(
                self, "确认重置",
                "确定要移除自定义源设置，恢复默认吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    for scope in ["global", "user"]:
                        subprocess.run(
                            PIP_COMMAND_LIST + ["config", "unset", f"{scope}.index-url"],
                            capture_output=True, check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )
                    self.log("✅ 已重置 pip 源\n")
                    self.status_label.setText("已重置为默认源")
                    QMessageBox.information(self, "成功", "已重置为默认 PyPI 源")
                except Exception as e:
                    self.log(f"❌ 重置源失败: {e}\n")
                    QMessageBox.critical(self, "错误", f"重置源失败: {e}")
            return
        
        if not (new_source.startswith("http://") or new_source.startswith("https://")):
            QMessageBox.warning(self, "格式错误", "源地址必须以 http:// 或 https:// 开头")
            return
        
        # 设置新源
        command = PIP_COMMAND_LIST + ["config", "set", "global.index-url", new_source]
        self.run_pip_command(command, f"设置源为 {new_source}")
    
    def closeEvent(self, event):
        """关闭窗口时清理线程。"""
        for thread in self.active_threads:
            if thread.isRunning():
                thread.terminate()
                thread.wait(1000)
        event.accept()


def main():
    """主入口函数。"""
    # 检查依赖
    try:
        from packaging.version import parse
    except ImportError:
        print("错误: 需要 'packaging' 库。请运行: pip install packaging")
        sys.exit(1)
    
    # 检查 pip (非致命检查，允许应用启动)
    pip_ok = False
    try:
        result = subprocess.run(
            PIP_COMMAND_LIST + ["--version"], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        pip_ok = result.returncode == 0
        if not pip_ok:
            print(f"警告: pip 检查失败: {result.stderr}")
    except Exception as e:
        print(f"警告: 无法验证 pip: {e}")
    
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(STYLE_SHEET)
    
    window = PipToolboxWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

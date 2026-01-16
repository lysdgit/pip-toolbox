"""
pip 命令工具模块
包含 pip 命令执行、版本获取、源管理等功能
"""
import subprocess
import shutil
import os
import re
import time
import pkg_resources
from packaging.version import parse as parse_version

# --- 配置 ---
PIP_COMMAND = shutil.which("pip3") or shutil.which("pip") or "pip"

# --- 全局缓存 ---
global_version_cache = {}  # 键为包名，值为 (版本列表, 时间戳)


# --- 辅助函数 ---
def get_installed_packages():
    """获取所有已安装的 pip 包及其版本。"""
    pkg_resources._initialize_master_working_set()
    return sorted([(pkg.key, pkg.version) for pkg in pkg_resources.working_set])


def get_current_source():
    """获取当前配置的 pip 索引 URL。"""
    try:
        for scope in ["global", "user"]:
            result = subprocess.run(
                [PIP_COMMAND, "config", "get", f"{scope}.index-url"],
                capture_output=True, text=True, encoding="utf-8", check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        return "默认 PyPI 源"
    except Exception as e:
        print(f"获取当前源出错: {e}")
        return "无法获取"


def list_rc_versions(package_name):
    """获取包的 RC (Release Candidate) 版本列表。"""
    result = subprocess.run(
        ["pip", "install", f"{package_name}==0.0.89rc1", "--pre"],
        capture_output=True,
        text=True
    )
    m = re.search(r"from versions: (.+?)\)", result.stderr, re.DOTALL)
    if not m:
        return []

    versions = [v.strip() for v in m.group(1).split(",")]
    rc_versions = [v for v in versions if "rc" in v.lower()]
    return rc_versions


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
            if not cleaned_line:
                continue
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
    
    rc_list = list_rc_versions(pkg_name)
    for rc_v in rc_list:
        try:
            valid_versions.append(parse_version(rc_v))
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
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", timeout=25,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
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


def run_pip_command_sync(command, action_name, callback):
    """
    运行 pip 命令的同步部分，在线程中执行。
    
    Args:
        command: pip 命令列表
        action_name: 操作名称，用于日志
        callback: 完成后的回调函数，接收 (log_message, success) 参数
    """
    output_log = ""
    success = False
    
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        stdout, stderr = process.communicate(timeout=600)
        
        if process.returncode == 0:
            output_log = f"✅ {action_name} 成功。\n--- 输出 ---\n{stdout}\n"
            if stderr:
                output_log += f"--- 警告/信息 ---\n{stderr}\n"
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
    
    callback(output_log, success)


def fetch_available_versions(pkg_name):
    """
    获取包的所有可用版本。
    
    Returns:
        tuple: (版本字符串列表, 解析后的版本列表)
    """
    if pkg_name in global_version_cache:
        versions, timestamp = global_version_cache[pkg_name]
        if time.time() - timestamp < 300:
            return versions, versions
    
    try:
        command = [PIP_COMMAND, "index", "versions", pkg_name]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", timeout=35,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode != 0 or "ERROR:" in result.stderr or \
           "Could not find" in result.stderr or "No matching index versions found" in result.stderr:
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
        return available_versions_str, parsed_versions
        
    except subprocess.TimeoutExpired:
        global_version_cache[pkg_name] = ([], time.time())
        return ["查询超时"], []
    except Exception as e:
        print(f"获取 {pkg_name} 版本出错: {e}")
        global_version_cache[pkg_name] = ([], time.time())
        return ["查询出错"], []

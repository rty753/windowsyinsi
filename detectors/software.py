"""Software/settings detectors: Location, RDP, Telemetry, Cortana, AdID, etc."""

import subprocess
import winreg
import json


def _run_ps(cmd, timeout=10):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _reg_read(hive, path, name, default=None):
    """Read a registry value, return default if not found."""
    try:
        with winreg.OpenKey(hive, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return default


class LocationDetector:
    name = "定位服务"
    key = "location"
    icon = "📍"

    @staticmethod
    def detect():
        result = {
            "name": LocationDetector.name,
            "key": LocationDetector.key,
            "icon": LocationDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        # Check location service (lfsvc)
        svc_out = _run_cmd("sc query lfsvc")
        svc_running = "RUNNING" in svc_out

        # Check system-level location setting
        consent = _reg_read(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
            "Value",
            "Deny",
        )

        # Check per-user setting
        user_consent = _reg_read(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
            "Value",
            "Deny",
        )

        location_enabled = consent == "Allow" or user_consent == "Allow"

        if location_enabled or svc_running:
            result["enabled"] = True
            result["status"] = "warning"
            parts = []
            if location_enabled:
                parts.append("定位权限已开启")
            if svc_running:
                parts.append("lfsvc 服务运行中")
            result["description"] = ", ".join(parts)
        else:
            result["description"] = "定位服务已关闭"

        result["details"].append(f"系统定位权限: {consent}")
        result["details"].append(f"用户定位权限: {user_consent}")
        result["details"].append(
            f"lfsvc 服务: {'运行中' if svc_running else '已停止'}"
        )

        # List apps with location permission
        try:
            base = (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion"
                r"\CapabilityAccessManager\ConsentStore\location"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        i += 1
                        if subkey_name == "NonPackaged":
                            continue
                        try:
                            val = _reg_read(
                                winreg.HKEY_CURRENT_USER,
                                f"{base}\\{subkey_name}",
                                "Value",
                                "Deny",
                            )
                            if val == "Allow":
                                result["details"].append(
                                    f"[定位权限] {subkey_name}"
                                )
                        except Exception:
                            pass
                    except OSError:
                        break
        except OSError:
            pass

        return result


class RDPDetector:
    name = "远程桌面(RDP)"
    key = "rdp"
    icon = "🖥️"

    @staticmethod
    def detect():
        result = {
            "name": RDPDetector.name,
            "key": RDPDetector.key,
            "icon": RDPDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        # fDenyTSConnections: 0 = RDP enabled, 1 = RDP disabled
        deny = _reg_read(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Terminal Server",
            "fDenyTSConnections",
            1,
        )

        if deny == 0:
            result["enabled"] = True
            result["status"] = "active"
            result["description"] = "远程桌面已启用 (可被远程连接!)"

            # Check if NLA is required
            nla = _reg_read(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Terminal Server"
                r"\WinStations\RDP-Tcp",
                "UserAuthentication",
                0,
            )
            result["details"].append(
                f"网络级别认证(NLA): {'已启用' if nla == 1 else '未启用'}"
            )

            # Check RDP port
            port = _reg_read(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Terminal Server"
                r"\WinStations\RDP-Tcp",
                "PortNumber",
                3389,
            )
            result["details"].append(f"RDP 端口: {port}")
        else:
            result["description"] = "远程桌面已禁用"
            result["details"].append("fDenyTSConnections = 1")

        return result


TELEMETRY_LEVELS = {
    0: "Security (安全级别 - 最低)",
    1: "Basic (基本)",
    2: "Enhanced (增强)",
    3: "Full (完整 - 最高)",
}


class TelemetryDetector:
    name = "诊断数据"
    key = "telemetry"
    icon = "📊"

    @staticmethod
    def detect():
        result = {
            "name": TelemetryDetector.name,
            "key": TelemetryDetector.key,
            "icon": TelemetryDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        # Check policy level first
        level = _reg_read(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
            "AllowTelemetry",
            None,
        )

        if level is None:
            # Check system setting
            level = _reg_read(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion"
                r"\Policies\DataCollection",
                "AllowTelemetry",
                3,  # Default is Full
            )

        level_desc = TELEMETRY_LEVELS.get(level, f"未知级别({level})")

        if level is not None and level > 0:
            result["enabled"] = True
            result["status"] = "warning" if level <= 1 else "active"
            result["description"] = f"遥测级别: {level_desc}"
        else:
            result["description"] = f"遥测级别: {level_desc}"

        result["details"].append(f"AllowTelemetry = {level}")
        result["details"].append(f"级别说明: {level_desc}")

        # Check DiagTrack service
        svc_out = _run_cmd("sc query DiagTrack")
        if "RUNNING" in svc_out:
            result["details"].append("DiagTrack 服务: 运行中")
        else:
            result["details"].append("DiagTrack 服务: 已停止")

        return result


class CortanaDetector:
    name = "Cortana"
    key = "cortana"
    icon = "🤖"

    @staticmethod
    def detect():
        result = {
            "name": CortanaDetector.name,
            "key": CortanaDetector.key,
            "icon": CortanaDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        # Check policy
        allow = _reg_read(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
            "AllowCortana",
            None,
        )

        if allow is None:
            # Check user setting
            consent = _reg_read(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
                "CortanaConsent",
                None,
            )
            if consent is not None:
                allow = consent

        # Check BingSearchEnabled as additional indicator
        bing = _reg_read(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
            "BingSearchEnabled",
            None,
        )

        if allow is None:
            # Default: assume enabled on consumer Windows
            result["status"] = "warning"
            result["description"] = "Cortana 状态未明确配置 (可能已启用)"
            result["enabled"] = True
            result["details"].append("AllowCortana: 未设置 (默认启用)")
        elif allow == 0:
            result["description"] = "Cortana 已禁用"
            result["details"].append("AllowCortana = 0")
        else:
            result["enabled"] = True
            result["status"] = "warning"
            result["description"] = "Cortana 已启用"
            result["details"].append(f"AllowCortana = {allow}")

        if bing is not None:
            result["details"].append(
                f"Bing 搜索: {'已启用' if bing else '已禁用'}"
            )

        return result


class AdvertisingIDDetector:
    name = "广告 ID"
    key = "ad_id"
    icon = "🏷️"

    @staticmethod
    def detect():
        result = {
            "name": AdvertisingIDDetector.name,
            "key": AdvertisingIDDetector.key,
            "icon": AdvertisingIDDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        enabled = _reg_read(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
            "Enabled",
            1,  # Default enabled
        )

        if enabled:
            result["enabled"] = True
            result["status"] = "warning"
            result["description"] = "广告 ID 追踪已启用"

            # Try to read the actual advertising ID
            ad_id = _reg_read(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
                "Id",
                None,
            )
            if ad_id:
                result["details"].append(f"广告 ID: {ad_id[:8]}...")
        else:
            result["description"] = "广告 ID 追踪已禁用"

        result["details"].append(f"Enabled = {enabled}")
        return result


class BackgroundAppsDetector:
    name = "应用后台运行"
    key = "bg_apps"
    icon = "⚙️"

    @staticmethod
    def detect():
        result = {
            "name": BackgroundAppsDetector.name,
            "key": BackgroundAppsDetector.key,
            "icon": BackgroundAppsDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        # Check global background apps setting
        global_disabled = _reg_read(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
            "GlobalUserDisabled",
            0,
        )

        if global_disabled:
            result["description"] = "后台应用运行已全局禁用"
            result["details"].append("GlobalUserDisabled = 1")
            return result

        result["enabled"] = True
        result["status"] = "warning"

        # Count apps with background access
        bg_apps = []
        try:
            base = (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion"
                r"\BackgroundAccessApplications"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as key:
                i = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(key, i)
                        i += 1
                        disabled = _reg_read(
                            winreg.HKEY_CURRENT_USER,
                            f"{base}\\{app_name}",
                            "Disabled",
                            0,
                        )
                        if not disabled:
                            bg_apps.append(app_name)
                    except OSError:
                        break
        except OSError:
            pass

        result["description"] = f"后台运行已开启, {len(bg_apps)} 个应用有后台权限"
        for app in bg_apps[:10]:
            short = app if len(app) < 50 else app[:47] + "..."
            result["details"].append(f"[后台运行] {short}")
        if len(bg_apps) > 10:
            result["details"].append(f"... 还有 {len(bg_apps) - 10} 个应用")

        return result


class ClipboardDetector:
    name = "剪贴板历史"
    key = "clipboard"
    icon = "📋"

    @staticmethod
    def detect():
        result = {
            "name": ClipboardDetector.name,
            "key": ClipboardDetector.key,
            "icon": ClipboardDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        history = _reg_read(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Clipboard",
            "EnableClipboardHistory",
            0,
        )

        cloud = _reg_read(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Clipboard",
            "EnableCloudClipboard",
            0,
        )

        issues = []
        if history:
            issues.append("剪贴板历史已启用")
        if cloud:
            issues.append("云同步剪贴板已启用")

        if issues:
            result["enabled"] = True
            result["status"] = "active" if cloud else "warning"
            result["description"] = ", ".join(issues)
        else:
            result["description"] = "剪贴板历史和云同步均已关闭"

        result["details"].append(f"EnableClipboardHistory = {history}")
        result["details"].append(f"EnableCloudClipboard = {cloud}")

        return result

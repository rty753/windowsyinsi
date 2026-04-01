"""Hardware device detectors: Camera, Microphone, Bluetooth, WiFi, USB Camera, Sensor."""

import subprocess
import winreg
import json
import re


def _run_ps(cmd, timeout=10):
    """Run a PowerShell command and return stdout."""
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
    """Run a shell command and return stdout."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _read_consent_store(device_type):
    """Read CapabilityAccessManager ConsentStore for webcam/microphone.

    Returns list of dicts with app info and whether currently in use.
    """
    results = []
    base_path = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion"
        r"\CapabilityAccessManager\ConsentStore\{}"
    ).format(device_type)

    for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        try:
            with winreg.OpenKey(hive, base_path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        i += 1
                        _read_consent_subkey(
                            hive, base_path, subkey_name, results
                        )
                    except OSError:
                        break
        except OSError:
            pass

    return results


def _read_consent_subkey(hive, base_path, subkey_name, results):
    """Read a single consent store subkey (app or NonPackaged container)."""
    full_path = f"{base_path}\\{subkey_name}"
    try:
        with winreg.OpenKey(hive, full_path) as sk:
            if subkey_name == "NonPackaged":
                j = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(sk, j)
                        j += 1
                        app_path = f"{full_path}\\{app_name}"
                        _read_app_consent(hive, app_path, app_name, results)
                    except OSError:
                        break
            else:
                _read_app_consent(hive, full_path, subkey_name, results)
    except OSError:
        pass


def _read_app_consent(hive, path, app_name, results):
    """Read consent values for a single app entry."""
    try:
        with winreg.OpenKey(hive, path) as app_key:
            try:
                start, _ = winreg.QueryValueEx(app_key, "LastUsedTimeStart")
            except OSError:
                start = 0
            try:
                stop, _ = winreg.QueryValueEx(app_key, "LastUsedTimeStop")
            except OSError:
                stop = 0

            in_use = (start != 0 and stop == 0) or (start > stop and start != 0)

            display_name = app_name.replace("#", "\\").replace("\\\\", "\\")
            if len(display_name) > 60:
                display_name = "..." + display_name[-57:]

            results.append({
                "app": display_name,
                "in_use": in_use,
                "last_start": start,
                "last_stop": stop,
            })
    except OSError:
        pass


class CameraDetector:
    name = "摄像头"
    key = "camera"
    icon = "📷"

    @staticmethod
    def detect():
        result = {
            "name": CameraDetector.name,
            "key": CameraDetector.key,
            "icon": CameraDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": False,
            "details": [],
            "can_disable": True,
        }

        # Check if camera device exists
        ps_out = _run_ps(
            "Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | "
            "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
        )

        if not ps_out:
            # Also check for Image class (some webcams register there)
            ps_out = _run_ps(
                "Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | "
                "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
            )

        if not ps_out:
            result["description"] = "未检测到摄像头设备"
            return result

        try:
            devices = json.loads(ps_out)
            if isinstance(devices, dict):
                devices = [devices]
        except json.JSONDecodeError:
            result["description"] = "设备信息解析失败"
            result["status"] = "warning"
            return result

        result["exists"] = True

        enabled_devices = [d for d in devices if d.get("Status") == "OK"]
        disabled_devices = [d for d in devices if d.get("Status") != "OK"]

        if not enabled_devices:
            result["description"] = f"摄像头已禁用 ({len(disabled_devices)} 个设备)"
            result["enabled"] = False
            result["status"] = "safe"
            for d in devices:
                result["details"].append(
                    f"[已禁用] {d.get('FriendlyName', '未知')}"
                )
            return result

        result["enabled"] = True

        # Check if camera is currently in use via ConsentStore
        consent = _read_consent_store("webcam")
        in_use_apps = [c for c in consent if c["in_use"]]

        if in_use_apps:
            apps_str = ", ".join(c["app"] for c in in_use_apps[:3])
            result["status"] = "active"
            result["description"] = f"摄像头正在被使用: {apps_str}"
            for c in in_use_apps:
                result["details"].append(f"[使用中] {c['app']}")
        else:
            result["status"] = "warning"
            result["description"] = (
                f"摄像头已启用 ({len(enabled_devices)} 个), 当前未被占用"
            )

        for d in enabled_devices:
            result["details"].append(
                f"[已启用] {d.get('FriendlyName', '未知')}"
            )

        return result


class MicrophoneDetector:
    name = "麦克风"
    key = "microphone"
    icon = "🎤"

    @staticmethod
    def detect():
        result = {
            "name": MicrophoneDetector.name,
            "key": MicrophoneDetector.key,
            "icon": MicrophoneDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": False,
            "details": [],
            "can_disable": True,
        }

        # Check audio endpoint devices (microphones)
        ps_out = _run_ps(
            "Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | "
            "Where-Object { $_.FriendlyName -like '*Microphone*' -or "
            "$_.FriendlyName -like '*麦克风*' -or "
            "$_.FriendlyName -like '*Mic*' } | "
            "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
        )

        if not ps_out:
            # Broader search
            ps_out = _run_ps(
                "Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | "
                "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
            )

        devices = []
        if ps_out:
            try:
                parsed = json.loads(ps_out)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                devices = parsed
            except json.JSONDecodeError:
                pass

        # Also check Media class for capture devices
        ps_out2 = _run_ps(
            "Get-PnpDevice -Class Media -ErrorAction SilentlyContinue | "
            "Where-Object { $_.FriendlyName -like '*Microphone*' -or "
            "$_.FriendlyName -like '*Audio*Input*' } | "
            "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
        )
        if ps_out2:
            try:
                parsed2 = json.loads(ps_out2)
                if isinstance(parsed2, dict):
                    parsed2 = [parsed2]
                devices.extend(parsed2)
            except json.JSONDecodeError:
                pass

        if not devices:
            result["description"] = "未检测到麦克风设备"
            return result

        result["exists"] = True
        enabled = [d for d in devices if d.get("Status") == "OK"]

        if not enabled:
            result["description"] = f"麦克风已禁用 ({len(devices)} 个设备)"
            result["enabled"] = False
            for d in devices:
                result["details"].append(
                    f"[已禁用] {d.get('FriendlyName', '未知')}"
                )
            return result

        result["enabled"] = True

        # Check consent store
        consent = _read_consent_store("microphone")
        in_use = [c for c in consent if c["in_use"]]

        if in_use:
            apps_str = ", ".join(c["app"] for c in in_use[:3])
            result["status"] = "active"
            result["description"] = f"麦克风正在被使用: {apps_str}"
            for c in in_use:
                result["details"].append(f"[使用中] {c['app']}")
        else:
            result["status"] = "warning"
            result["description"] = (
                f"麦克风已启用 ({len(enabled)} 个), 当前未被占用"
            )

        for d in enabled:
            result["details"].append(
                f"[已启用] {d.get('FriendlyName', '未知')}"
            )

        return result


class BluetoothDetector:
    name = "蓝牙"
    key = "bluetooth"
    icon = "📶"

    @staticmethod
    def detect():
        result = {
            "name": BluetoothDetector.name,
            "key": BluetoothDetector.key,
            "icon": BluetoothDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": False,
            "details": [],
            "can_disable": True,
        }

        ps_out = _run_ps(
            "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
            "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
        )

        if not ps_out:
            result["description"] = "未检测到蓝牙适配器"
            return result

        try:
            devices = json.loads(ps_out)
            if isinstance(devices, dict):
                devices = [devices]
        except json.JSONDecodeError:
            result["description"] = "蓝牙信息解析失败"
            result["status"] = "warning"
            return result

        result["exists"] = True

        # Filter for adapter (usually the radio device)
        adapters = [
            d for d in devices
            if d.get("Status") == "OK"
        ]

        if not adapters:
            result["description"] = "蓝牙适配器已禁用"
            result["enabled"] = False
            for d in devices:
                result["details"].append(
                    f"[已禁用] {d.get('FriendlyName', '未知')}"
                )
            return result

        result["enabled"] = True
        result["status"] = "warning"
        result["description"] = f"蓝牙已开启 ({len(adapters)} 个活跃设备)"

        # Check discoverable status via registry
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
            ):
                result["details"].append("蓝牙设备注册表可访问")
        except OSError:
            pass

        for d in adapters:
            result["details"].append(
                f"[已启用] {d.get('FriendlyName', '未知')}"
            )

        return result


class WiFiDetector:
    name = "WiFi"
    key = "wifi"
    icon = "📡"

    @staticmethod
    def detect():
        result = {
            "name": WiFiDetector.name,
            "key": WiFiDetector.key,
            "icon": WiFiDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": False,
            "details": [],
            "can_disable": True,
        }

        # Check interface status
        iface_out = _run_cmd("netsh interface show interface")

        wifi_line = None
        for line in iface_out.splitlines():
            lower = line.lower()
            if "wi-fi" in lower or "wifi" in lower or "wireless" in lower or "wlan" in lower:
                wifi_line = line
                break

        if not wifi_line:
            result["description"] = "未检测到 WiFi 适配器"
            return result

        result["exists"] = True

        if "Disabled" in wifi_line or "已禁用" in wifi_line:
            result["description"] = "WiFi 适配器已禁用"
            result["enabled"] = False
            return result

        result["enabled"] = True
        result["status"] = "warning"

        # Get connected SSID
        wlan_out = _run_cmd("netsh wlan show interfaces")
        ssid = ""
        state = ""
        for line in wlan_out.splitlines():
            stripped = line.strip()
            if stripped.startswith("SSID") and "BSSID" not in stripped:
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
            if "State" in stripped or "状态" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    state = parts[1].strip()

        if ssid:
            result["status"] = "active"
            result["description"] = f"WiFi 已连接: {ssid}"
            result["details"].append(f"SSID: {ssid}")
            result["details"].append(f"状态: {state}")
        else:
            result["description"] = "WiFi 已开启, 未连接网络"

        return result


class USBCameraDetector:
    name = "USB摄像头"
    key = "usb_camera"
    icon = "🔌"

    @staticmethod
    def detect():
        result = {
            "name": USBCameraDetector.name,
            "key": USBCameraDetector.key,
            "icon": USBCameraDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": False,
            "details": [],
            "can_disable": True,
        }

        # Query USB video devices
        ps_out = _run_ps(
            "Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InstanceId -like 'USB*' } | "
            "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
        )

        if not ps_out:
            # Also check Image class
            ps_out = _run_ps(
                "Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | "
                "Where-Object { $_.InstanceId -like 'USB*' } | "
                "Select-Object Status, FriendlyName, InstanceId | ConvertTo-Json"
            )

        if not ps_out:
            result["description"] = "未检测到 USB 摄像头设备"
            return result

        try:
            devices = json.loads(ps_out)
            if isinstance(devices, dict):
                devices = [devices]
        except json.JSONDecodeError:
            result["description"] = "USB 设备信息解析失败"
            result["status"] = "warning"
            return result

        result["exists"] = True
        enabled = [d for d in devices if d.get("Status") == "OK"]

        if enabled:
            result["enabled"] = True
            result["status"] = "warning"
            result["description"] = f"检测到 {len(enabled)} 个 USB 摄像头已启用"
            for d in enabled:
                result["details"].append(
                    f"[已启用] {d.get('FriendlyName', '未知')} "
                    f"({d.get('InstanceId', '')[:30]})"
                )
        else:
            result["description"] = f"USB 摄像头已禁用 ({len(devices)} 个设备)"
            for d in devices:
                result["details"].append(
                    f"[已禁用] {d.get('FriendlyName', '未知')}"
                )

        return result


class SensorDetector:
    name = "传感器服务"
    key = "sensor"
    icon = "🌡️"

    @staticmethod
    def detect():
        result = {
            "name": SensorDetector.name,
            "key": SensorDetector.key,
            "icon": SensorDetector.icon,
            "status": "safe",
            "description": "",
            "enabled": False,
            "exists": True,
            "details": [],
            "can_disable": True,
        }

        svc_out = _run_cmd("sc query SensorService")

        if "RUNNING" in svc_out:
            result["enabled"] = True
            result["status"] = "warning"
            result["description"] = "传感器服务正在运行"
            result["details"].append("SensorService: RUNNING")
        elif "STOPPED" in svc_out:
            result["description"] = "传感器服务已停止"
            result["details"].append("SensorService: STOPPED")
        else:
            result["description"] = "传感器服务状态未知"
            result["status"] = "warning"
            result["details"].append(f"查询结果: {svc_out[:100]}")

        # Also check SensorDataService and SensrSvc
        for svc_name, display in [
            ("SensorDataService", "传感器数据服务"),
            ("SensrSvc", "传感器监控服务"),
        ]:
            svc_out2 = _run_cmd(f"sc query {svc_name}")
            if "RUNNING" in svc_out2:
                result["details"].append(f"{svc_name}: RUNNING")
                result["enabled"] = True
                result["status"] = "warning"
            elif "STOPPED" in svc_out2:
                result["details"].append(f"{svc_name}: STOPPED")

        if result["status"] == "safe":
            result["description"] = "所有传感器服务已停止"

        return result

"""Privacy control actions: enable/disable devices, services, registry settings."""

import subprocess
import winreg
import logging

logger = logging.getLogger("PrivacyGuard")


def _run_ps(cmd, timeout=15):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0, r.stdout.strip() + r.stderr.strip()
    except Exception as e:
        return False, str(e)


def _run_cmd(cmd, timeout=15):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0, r.stdout.strip() + r.stderr.strip()
    except Exception as e:
        return False, str(e)


def _reg_set(hive, path, name, value, reg_type=winreg.REG_DWORD):
    """Set a registry value, creating the key if needed."""
    try:
        with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, reg_type, value)
        return True, f"注册表已设置: {name} = {value}"
    except OSError as e:
        return False, f"注册表设置失败: {e}"


class PrivacyControls:
    """All privacy control actions."""

    @staticmethod
    def disable_camera():
        """Disable all camera devices via Device Manager."""
        logger.info("操作: 禁用摄像头")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | "
            "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue; "
            "Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | "
            "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "摄像头禁用成功" if ok else f"摄像头禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_camera():
        logger.info("操作: 启用摄像头")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | "
            "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue; "
            "Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | "
            "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "摄像头启用成功" if ok else f"摄像头启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_microphone():
        logger.info("操作: 禁用麦克风")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | "
            "Where-Object { $_.FriendlyName -like '*Microphone*' -or "
            "$_.FriendlyName -like '*麦克风*' -or "
            "$_.FriendlyName -like '*Mic*' } | "
            "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "麦克风禁用成功" if ok else f"麦克风禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_microphone():
        logger.info("操作: 启用麦克风")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | "
            "Where-Object { $_.FriendlyName -like '*Microphone*' -or "
            "$_.FriendlyName -like '*麦克风*' -or "
            "$_.FriendlyName -like '*Mic*' } | "
            "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "麦克风启用成功" if ok else f"麦克风启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_location():
        logger.info("操作: 禁用定位服务")
        results = []

        # Disable lfsvc service
        ok1, msg1 = _run_cmd("sc stop lfsvc")
        ok2, msg2 = _run_cmd("sc config lfsvc start= disabled")
        results.append(f"lfsvc 服务: {'已停止' if ok1 else msg1}")

        # Set registry to deny
        ok3, msg3 = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion"
            r"\CapabilityAccessManager\ConsentStore\location",
            "Value", "Deny", winreg.REG_SZ,
        )
        results.append(msg3)

        ok4, msg4 = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion"
            r"\CapabilityAccessManager\ConsentStore\location",
            "Value", "Deny", winreg.REG_SZ,
        )
        results.append(msg4)

        combined = "; ".join(results)
        logger.info(f"结果: {combined}")
        return ok3 or ok4, combined

    @staticmethod
    def enable_location():
        logger.info("操作: 启用定位服务")
        _run_cmd("sc config lfsvc start= auto")
        _run_cmd("sc start lfsvc")
        ok, msg = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion"
            r"\CapabilityAccessManager\ConsentStore\location",
            "Value", "Allow", winreg.REG_SZ,
        )
        logger.info(f"结果: {msg}")
        return ok, msg

    @staticmethod
    def disable_bluetooth():
        logger.info("操作: 禁用蓝牙")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Status -eq 'OK' } | "
            "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "蓝牙禁用成功" if ok else f"蓝牙禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_bluetooth():
        logger.info("操作: 启用蓝牙")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
            "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "蓝牙启用成功" if ok else f"蓝牙启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_wifi():
        logger.info("操作: 禁用 WiFi")
        # Try common interface names
        for name in ["Wi-Fi", "WiFi", "Wireless", "WLAN"]:
            ok, msg = _run_cmd(
                f'netsh interface set interface "{name}" disable'
            )
            if ok:
                logger.info(f"结果: WiFi ({name}) 禁用成功")
                return True, f"WiFi ({name}) 禁用成功"

        # Fallback: try PowerShell
        ok, msg = _run_ps(
            "Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*Wi*Fi*' "
            "-or $_.InterfaceDescription -like '*Wireless*' } | Disable-NetAdapter -Confirm:$false"
        )
        result = "WiFi 禁用成功" if ok else f"WiFi 禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_wifi():
        logger.info("操作: 启用 WiFi")
        for name in ["Wi-Fi", "WiFi", "Wireless", "WLAN"]:
            ok, msg = _run_cmd(
                f'netsh interface set interface "{name}" enable'
            )
            if ok:
                logger.info(f"结果: WiFi ({name}) 启用成功")
                return True, f"WiFi ({name}) 启用成功"

        ok, msg = _run_ps(
            "Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*Wi*Fi*' "
            "-or $_.InterfaceDescription -like '*Wireless*' } | Enable-NetAdapter -Confirm:$false"
        )
        result = "WiFi 启用成功" if ok else f"WiFi 启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_usb_camera():
        logger.info("操作: 禁用 USB 摄像头")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InstanceId -like 'USB*' } | "
            "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue; "
            "Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InstanceId -like 'USB*' } | "
            "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "USB 摄像头禁用成功" if ok else f"USB 摄像头禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_usb_camera():
        logger.info("操作: 启用 USB 摄像头")
        ok, msg = _run_ps(
            "Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InstanceId -like 'USB*' } | "
            "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue; "
            "Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InstanceId -like 'USB*' } | "
            "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
        )
        result = "USB 摄像头启用成功" if ok else f"USB 摄像头启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_sensor():
        logger.info("操作: 禁用传感器服务")
        results = []
        for svc in ["SensorService", "SensorDataService", "SensrSvc"]:
            ok1, _ = _run_cmd(f"sc stop {svc}")
            ok2, _ = _run_cmd(f"sc config {svc} start= disabled")
            results.append(
                f"{svc}: {'已停止并禁用' if ok1 or ok2 else '操作失败'}"
            )
        combined = "; ".join(results)
        logger.info(f"结果: {combined}")
        return True, combined

    @staticmethod
    def enable_sensor():
        logger.info("操作: 启用传感器服务")
        results = []
        for svc in ["SensorService", "SensorDataService", "SensrSvc"]:
            _run_cmd(f"sc config {svc} start= auto")
            ok, _ = _run_cmd(f"sc start {svc}")
            results.append(f"{svc}: {'已启动' if ok else '启动失败'}")
        combined = "; ".join(results)
        logger.info(f"结果: {combined}")
        return True, combined

    @staticmethod
    def disable_rdp():
        logger.info("操作: 禁用远程桌面")
        ok, msg = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Terminal Server",
            "fDenyTSConnections", 1,
        )
        # Also disable the firewall rule
        _run_cmd(
            'netsh advfirewall firewall set rule group="remote desktop" new enable=No'
        )
        result = "远程桌面已禁用" if ok else f"禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_rdp():
        logger.info("操作: 启用远程桌面")
        ok, msg = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Terminal Server",
            "fDenyTSConnections", 0,
        )
        _run_cmd(
            'netsh advfirewall firewall set rule group="remote desktop" new enable=Yes'
        )
        result = "远程桌面已启用" if ok else f"启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_telemetry():
        logger.info("操作: 设置诊断数据为最低级别")
        results = []

        ok1, msg1 = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
            "AllowTelemetry", 0,
        )
        results.append(msg1)

        ok2, msg2 = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
            "AllowTelemetry", 0,
        )
        results.append(msg2)

        # Stop DiagTrack service
        ok3, _ = _run_cmd("sc stop DiagTrack")
        ok4, _ = _run_cmd("sc config DiagTrack start= disabled")
        results.append(
            f"DiagTrack: {'已停止并禁用' if ok3 or ok4 else '操作失败'}"
        )

        combined = "; ".join(results)
        logger.info(f"结果: {combined}")
        return ok1 or ok2, combined

    @staticmethod
    def enable_telemetry():
        logger.info("操作: 恢复诊断数据设置")
        ok, msg = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
            "AllowTelemetry", 1,
        )
        _run_cmd("sc config DiagTrack start= auto")
        _run_cmd("sc start DiagTrack")
        logger.info(f"结果: {msg}")
        return ok, msg

    @staticmethod
    def disable_cortana():
        logger.info("操作: 禁用 Cortana")
        results = []

        ok1, msg1 = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
            "AllowCortana", 0,
        )
        results.append(msg1)

        ok2, msg2 = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
            "CortanaConsent", 0,
        )
        results.append(msg2)

        ok3, msg3 = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
            "BingSearchEnabled", 0,
        )
        results.append(msg3)

        combined = "; ".join(results)
        logger.info(f"结果: {combined}")
        return ok1 or ok2, combined

    @staticmethod
    def enable_cortana():
        logger.info("操作: 启用 Cortana")
        ok, msg = _reg_set(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
            "AllowCortana", 1,
        )
        _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
            "CortanaConsent", 1,
        )
        logger.info(f"结果: {msg}")
        return ok, msg

    @staticmethod
    def disable_ad_id():
        logger.info("操作: 禁用广告 ID")
        ok, msg = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
            "Enabled", 0,
        )
        result = "广告 ID 已禁用" if ok else f"禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_ad_id():
        logger.info("操作: 启用广告 ID")
        ok, msg = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
            "Enabled", 1,
        )
        result = "广告 ID 已启用" if ok else f"启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_bg_apps():
        logger.info("操作: 禁用后台应用运行")
        ok, msg = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
            "GlobalUserDisabled", 1,
        )
        result = "后台应用运行已全局禁用" if ok else f"禁用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def enable_bg_apps():
        logger.info("操作: 启用后台应用运行")
        ok, msg = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
            "GlobalUserDisabled", 0,
        )
        result = "后台应用运行已启用" if ok else f"启用失败: {msg}"
        logger.info(f"结果: {result}")
        return ok, result

    @staticmethod
    def disable_clipboard():
        logger.info("操作: 禁用剪贴板历史和云同步")
        results = []
        ok1, msg1 = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Clipboard",
            "EnableClipboardHistory", 0,
        )
        results.append(msg1)

        ok2, msg2 = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Clipboard",
            "EnableCloudClipboard", 0,
        )
        results.append(msg2)

        combined = "; ".join(results)
        logger.info(f"结果: {combined}")
        return ok1 or ok2, combined

    @staticmethod
    def enable_clipboard():
        logger.info("操作: 启用剪贴板历史")
        ok, msg = _reg_set(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Clipboard",
            "EnableClipboardHistory", 1,
        )
        logger.info(f"结果: {msg}")
        return ok, msg

    # Map of device key -> (disable_func, enable_func)
    CONTROL_MAP = {
        "camera": (disable_camera.__func__, enable_camera.__func__),
        "microphone": (disable_microphone.__func__, enable_microphone.__func__),
        "location": (disable_location.__func__, enable_location.__func__),
        "bluetooth": (disable_bluetooth.__func__, enable_bluetooth.__func__),
        "wifi": (disable_wifi.__func__, enable_wifi.__func__),
        "usb_camera": (disable_usb_camera.__func__, enable_usb_camera.__func__),
        "sensor": (disable_sensor.__func__, enable_sensor.__func__),
        "rdp": (disable_rdp.__func__, enable_rdp.__func__),
        "telemetry": (disable_telemetry.__func__, enable_telemetry.__func__),
        "cortana": (disable_cortana.__func__, enable_cortana.__func__),
        "ad_id": (disable_ad_id.__func__, enable_ad_id.__func__),
        "bg_apps": (disable_bg_apps.__func__, enable_bg_apps.__func__),
        "clipboard": (disable_clipboard.__func__, enable_clipboard.__func__),
    }

    @classmethod
    def toggle(cls, key, enable=False):
        """Toggle a device/feature. Returns (success, message)."""
        if key not in cls.CONTROL_MAP:
            return False, f"未知的控制项: {key}"
        disable_fn, enable_fn = cls.CONTROL_MAP[key]
        if enable:
            return enable_fn()
        else:
            return disable_fn()

    @classmethod
    def disable_all(cls):
        """Disable all privacy-sensitive devices/features.
        Returns list of (key, success, message).
        """
        logger.info("=" * 50)
        logger.info("执行: 一键禁用所有隐私设备")
        logger.info("=" * 50)

        results = []
        keys_to_disable = [
            "camera", "microphone", "location", "bluetooth", "wifi",
            "sensor", "rdp", "telemetry", "ad_id", "clipboard",
        ]
        for key in keys_to_disable:
            ok, msg = cls.toggle(key, enable=False)
            results.append((key, ok, msg))

        logger.info("一键禁用操作完成")
        return results

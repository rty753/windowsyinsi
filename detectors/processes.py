"""Process occupation detector for camera and microphone."""

import winreg
import os
import time

try:
    import psutil
except ImportError:
    psutil = None


def _filetime_to_unix(ft):
    """Convert Windows FILETIME (100-ns since 1601) to Unix timestamp."""
    if ft == 0:
        return 0
    EPOCH_DIFF = 116444736000000000  # 100-ns intervals between 1601 and 1970
    return (ft - EPOCH_DIFF) / 10_000_000


class ProcessDetector:
    """Detect which processes are currently using camera/microphone."""

    @staticmethod
    def get_device_processes(device_type="webcam"):
        """Get processes using a device (webcam or microphone).

        Returns list of dicts: {app, pid, path, start_time, in_use}
        """
        results = []
        base_path = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion"
            r"\CapabilityAccessManager\ConsentStore\{}"
        ).format(device_type)

        for hive in [winreg.HKEY_CURRENT_USER]:
            ProcessDetector._scan_consent_store(hive, base_path, results)

        # Enrich with psutil data
        if psutil:
            ProcessDetector._enrich_with_psutil(results)

        return results

    @staticmethod
    def _scan_consent_store(hive, base_path, results):
        try:
            with winreg.OpenKey(hive, base_path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        i += 1
                        if subkey_name == "NonPackaged":
                            ProcessDetector._scan_non_packaged(
                                hive, f"{base_path}\\NonPackaged", results
                            )
                        else:
                            ProcessDetector._read_app_entry(
                                hive, f"{base_path}\\{subkey_name}",
                                subkey_name, results, packaged=True,
                            )
                    except OSError:
                        break
        except OSError:
            pass

    @staticmethod
    def _scan_non_packaged(hive, path, results):
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(key, i)
                        i += 1
                        ProcessDetector._read_app_entry(
                            hive, f"{path}\\{app_name}",
                            app_name, results, packaged=False,
                        )
                    except OSError:
                        break
        except OSError:
            pass

    @staticmethod
    def _read_app_entry(hive, path, app_name, results, packaged=False):
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

                in_use = (start != 0 and stop == 0) or (
                    start > stop and start != 0
                )

                # Decode app path from registry name
                if not packaged:
                    exe_path = app_name.replace("#", "\\")
                else:
                    exe_path = app_name

                display_name = os.path.basename(exe_path) if "\\" in exe_path else exe_path

                entry = {
                    "app": display_name,
                    "full_path": exe_path,
                    "pid": None,
                    "start_time": _filetime_to_unix(start) if start else None,
                    "in_use": in_use,
                    "packaged": packaged,
                }
                results.append(entry)
        except OSError:
            pass

    @staticmethod
    def _enrich_with_psutil(results):
        """Try to match registry entries with running processes."""
        if not psutil:
            return

        for entry in results:
            if not entry["in_use"]:
                continue

            exe_name = entry["app"].lower()
            for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
                try:
                    info = proc.info
                    proc_name = (info.get("name") or "").lower()
                    proc_exe = (info.get("exe") or "").lower()

                    if exe_name in proc_name or exe_name in proc_exe:
                        entry["pid"] = info["pid"]
                        entry["full_path"] = info.get("exe") or entry["full_path"]
                        ct = info.get("create_time")
                        if ct:
                            entry["start_time"] = ct
                        break
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue

    @staticmethod
    def kill_process(pid):
        """Kill a process by PID. Returns (success, message)."""
        if not psutil:
            return False, "psutil 未安装"
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
            return True, f"已终止进程 {proc_name} (PID: {pid})"
        except psutil.NoSuchProcess:
            return False, f"进程 {pid} 不存在"
        except psutil.AccessDenied:
            return False, f"无权终止进程 {pid} (可能需要更高权限)"
        except Exception as e:
            return False, f"终止进程失败: {e}"

    @staticmethod
    def get_all_occupation():
        """Get all camera and microphone occupation info."""
        camera_procs = ProcessDetector.get_device_processes("webcam")
        mic_procs = ProcessDetector.get_device_processes("microphone")
        return {
            "camera": camera_procs,
            "microphone": mic_procs,
            "camera_active": [p for p in camera_procs if p["in_use"]],
            "mic_active": [p for p in mic_procs if p["in_use"]],
        }

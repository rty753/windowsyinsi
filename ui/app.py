"""Main application UI - Dashboard, Process View, Log View."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
import time
import os
import sys
from datetime import datetime

from detectors import ALL_DETECTORS
from detectors.processes import ProcessDetector
from controls.actions import PrivacyControls
from ui.tray import TrayIcon

logger = logging.getLogger("PrivacyGuard")

# ── Theme Colors ──────────────────────────────────────────────────────────
BG_DARK = "#1a2332"
BG_CARD = "#243447"
BG_CARD_HOVER = "#2d4159"
BG_HEADER = "#0f1923"
FG_PRIMARY = "#e8edf3"
FG_SECONDARY = "#8899aa"
FG_DIM = "#556677"
COLOR_SAFE = "#00c853"
COLOR_ACTIVE = "#ff1744"
COLOR_WARNING = "#ffc107"
COLOR_BTN = "#1e88e5"
COLOR_BTN_HOVER = "#2196f3"
COLOR_BTN_DANGER = "#d32f2f"
COLOR_BTN_DANGER_HOVER = "#f44336"
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")
FONT_NORMAL = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_MONO = ("Consolas", 9)


class DeviceRow(tk.Frame):
    """A single device status row in the dashboard."""

    def __init__(self, parent, device_info, toggle_callback, **kwargs):
        super().__init__(parent, bg=BG_CARD, **kwargs)
        self.device_info = device_info
        self.toggle_callback = toggle_callback
        self.key = device_info["key"]

        self.columnconfigure(1, weight=1)
        self.config(padx=8, pady=4)

        # Status light (canvas circle)
        self.light_canvas = tk.Canvas(
            self, width=20, height=20, bg=BG_CARD,
            highlightthickness=0,
        )
        self.light_canvas.grid(row=0, column=0, padx=(8, 6), pady=8)
        self.light_id = self.light_canvas.create_oval(
            3, 3, 17, 17, fill=COLOR_SAFE, outline=""
        )

        # Info frame (name + description)
        info_frame = tk.Frame(self, bg=BG_CARD)
        info_frame.grid(row=0, column=1, sticky="w", pady=4)

        icon = device_info.get("icon", "")
        self.name_label = tk.Label(
            info_frame,
            text=f"{icon} {device_info['name']}",
            bg=BG_CARD, fg=FG_PRIMARY, font=FONT_NORMAL,
            anchor="w",
        )
        self.name_label.pack(anchor="w")

        self.desc_label = tk.Label(
            info_frame,
            text=device_info.get("description", "检测中..."),
            bg=BG_CARD, fg=FG_SECONDARY, font=FONT_SMALL,
            anchor="w", wraplength=400,
        )
        self.desc_label.pack(anchor="w")

        # Details button
        self.detail_btn = tk.Button(
            self, text="详情",
            bg=BG_CARD_HOVER, fg=FG_SECONDARY,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            activebackground=BG_HEADER, activeforeground=FG_PRIMARY,
            command=self._show_details,
        )
        self.detail_btn.grid(row=0, column=2, padx=4, pady=8)

        # Toggle button
        self.toggle_btn = tk.Button(
            self, text="禁用",
            bg=COLOR_BTN, fg="white",
            font=FONT_SMALL, relief="flat", cursor="hand2", width=6,
            activebackground=COLOR_BTN_HOVER, activeforeground="white",
            command=self._on_toggle,
        )
        self.toggle_btn.grid(row=0, column=3, padx=(4, 8), pady=8)

        # Separator
        sep = tk.Frame(self, bg=FG_DIM, height=1)
        sep.grid(row=1, column=0, columnspan=4, sticky="ew")

    def update_status(self, info):
        """Update the row with new detection info."""
        self.device_info = info
        status = info.get("status", "safe")

        color_map = {"safe": COLOR_SAFE, "active": COLOR_ACTIVE, "warning": COLOR_WARNING}
        color = color_map.get(status, COLOR_SAFE)
        self.light_canvas.itemconfig(self.light_id, fill=color)

        icon = info.get("icon", "")
        self.name_label.config(text=f"{icon} {info['name']}")
        self.desc_label.config(text=info.get("description", ""))

        if info.get("enabled"):
            self.toggle_btn.config(
                text="禁用", bg=COLOR_BTN_DANGER,
                activebackground=COLOR_BTN_DANGER_HOVER,
            )
        else:
            self.toggle_btn.config(
                text="启用", bg=COLOR_BTN,
                activebackground=COLOR_BTN_HOVER,
            )

    def _on_toggle(self):
        enabled = self.device_info.get("enabled", False)
        action = "启用" if not enabled else "禁用"
        name = self.device_info["name"]

        if enabled:
            # Disabling - just do it
            self.toggle_btn.config(state="disabled", text="处理中...")
            self.toggle_callback(self.key, enable=False)
        else:
            # Enabling
            self.toggle_btn.config(state="disabled", text="处理中...")
            self.toggle_callback(self.key, enable=True)

    def _show_details(self):
        details = self.device_info.get("details", [])
        if not details:
            details = ["暂无详细信息"]

        win = tk.Toplevel(self.winfo_toplevel())
        win.title(f"{self.device_info['name']} - 详细信息")
        win.geometry("500x350")
        win.configure(bg=BG_DARK)
        win.transient(self.winfo_toplevel())

        tk.Label(
            win, text=f"{self.device_info.get('icon', '')} {self.device_info['name']}",
            bg=BG_DARK, fg=FG_PRIMARY, font=FONT_TITLE,
        ).pack(pady=(15, 5))

        tk.Label(
            win, text=self.device_info.get("description", ""),
            bg=BG_DARK, fg=FG_SECONDARY, font=FONT_NORMAL,
        ).pack(pady=(0, 10))

        text = scrolledtext.ScrolledText(
            win, bg=BG_CARD, fg=FG_PRIMARY, font=FONT_MONO,
            insertbackground=FG_PRIMARY, relief="flat",
            selectbackground=COLOR_BTN,
        )
        text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        for detail in details:
            text.insert("end", f"  {detail}\n")
        text.config(state="disabled")

    def enable_toggle(self):
        self.toggle_btn.config(state="normal")


class PrivacyGuardApp:
    """Main application window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Windows 隐私卫士")
        self.root.geometry("780x850")
        self.root.minsize(700, 600)
        self.root.configure(bg=BG_DARK)

        # Set window icon (if available)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.device_rows = {}
        self.device_data = {}
        self.monitoring = False
        self.monitor_interval = 30  # seconds
        self._prev_active = set()

        # Setup logging handler to capture log to UI
        self.log_handler = UILogHandler(self)
        self.log_handler.setLevel(logging.INFO)
        self.log_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S")
        )
        logging.getLogger("PrivacyGuard").addHandler(self.log_handler)

        # Also setup file logging
        self._setup_file_logging()

        # Tray icon
        self.tray = TrayIcon(
            show_callback=self._show_window,
            quit_callback=self._quit_app,
        )

        self._build_ui()

        # Handle window close -> minimize to tray
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Initial scan
        self.root.after(200, self._initial_scan)

    def _setup_file_logging(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(os.path.dirname(script_dir), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir, f"privacy_guard_{datetime.now():%Y%m%d}.log"
        )
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logging.getLogger("PrivacyGuard").addHandler(fh)

    def _build_ui(self):
        """Build the complete UI."""
        # ── Header ────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG_HEADER, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = tk.Frame(header, bg=BG_HEADER)
        title_frame.pack(side="left", padx=20, pady=10)

        tk.Label(
            title_frame,
            text="Windows 隐私卫士",
            bg=BG_HEADER, fg=FG_PRIMARY,
            font=("Microsoft YaHei UI", 16, "bold"),
        ).pack(anchor="w")

        self.status_label = tk.Label(
            title_frame,
            text="正在扫描设备状态...",
            bg=BG_HEADER, fg=FG_SECONDARY,
            font=FONT_SMALL,
        )
        self.status_label.pack(anchor="w")

        # Header buttons
        btn_frame = tk.Frame(header, bg=BG_HEADER)
        btn_frame.pack(side="right", padx=20, pady=10)

        self.disable_all_btn = tk.Button(
            btn_frame,
            text="  一键禁用所有隐私设备  ",
            bg=COLOR_BTN_DANGER, fg="white",
            font=("Microsoft YaHei UI", 11, "bold"),
            relief="flat", cursor="hand2",
            activebackground=COLOR_BTN_DANGER_HOVER,
            activeforeground="white",
            command=self._disable_all,
        )
        self.disable_all_btn.pack(side="right", padx=(10, 0))

        self.refresh_btn = tk.Button(
            btn_frame, text=" 刷新 ",
            bg=COLOR_BTN, fg="white",
            font=FONT_NORMAL, relief="flat", cursor="hand2",
            activebackground=COLOR_BTN_HOVER, activeforeground="white",
            command=self._refresh,
        )
        self.refresh_btn.pack(side="right", padx=(10, 0))

        # ── Notebook (tabs) ──────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=BG_DARK, borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=BG_CARD, foreground=FG_SECONDARY,
            padding=[15, 6], font=FONT_NORMAL,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", BG_HEADER)],
            foreground=[("selected", FG_PRIMARY)],
        )

        notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        notebook.pack(fill="both", expand=True, padx=10, pady=(5, 0))

        # Tab 1: Dashboard
        dash_frame = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(dash_frame, text="  设备总览  ")

        # Monitor toggle in dash
        monitor_bar = tk.Frame(dash_frame, bg=BG_DARK)
        monitor_bar.pack(fill="x", padx=5, pady=(5, 0))

        self.monitor_btn = tk.Button(
            monitor_bar, text=" 开启实时监控 ",
            bg="#2e7d32", fg="white",
            font=FONT_SMALL, relief="flat", cursor="hand2",
            activebackground="#43a047", activeforeground="white",
            command=self._toggle_monitor,
        )
        self.monitor_btn.pack(side="left")

        self.monitor_status = tk.Label(
            monitor_bar, text="监控: 关闭",
            bg=BG_DARK, fg=FG_DIM, font=FONT_SMALL,
        )
        self.monitor_status.pack(side="left", padx=10)

        # Scrollable device list
        canvas_frame = tk.Frame(dash_frame, bg=BG_DARK)
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.dash_canvas = tk.Canvas(canvas_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(
            canvas_frame, orient="vertical", command=self.dash_canvas.yview
        )
        self.dash_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.dash_canvas.pack(side="left", fill="both", expand=True)

        self.devices_frame = tk.Frame(self.dash_canvas, bg=BG_DARK)
        self.canvas_window = self.dash_canvas.create_window(
            (0, 0), window=self.devices_frame, anchor="nw"
        )

        self.devices_frame.bind("<Configure>", self._on_frame_configure)
        self.dash_canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling
        self.dash_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.dash_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"
            ),
        )

        # Tab 2: Process View
        proc_frame = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(proc_frame, text="  进程占用  ")
        self._build_process_tab(proc_frame)

        # Tab 3: Log View
        log_frame = tk.Frame(notebook, bg=BG_DARK)
        notebook.add(log_frame, text="  操作日志  ")
        self._build_log_tab(log_frame)

        # ── Bottom Status Bar ─────────────────────────────────────────────
        status_bar = tk.Frame(self.root, bg=BG_HEADER, height=28)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)

        self.bottom_status = tk.Label(
            status_bar, text="就绪",
            bg=BG_HEADER, fg=FG_DIM, font=FONT_SMALL,
            anchor="w",
        )
        self.bottom_status.pack(side="left", padx=10)

        self.time_label = tk.Label(
            status_bar, text="",
            bg=BG_HEADER, fg=FG_DIM, font=FONT_SMALL,
            anchor="e",
        )
        self.time_label.pack(side="right", padx=10)
        self._update_time()

    def _build_process_tab(self, parent):
        """Build the process occupation tab."""
        top_bar = tk.Frame(parent, bg=BG_DARK)
        top_bar.pack(fill="x", padx=10, pady=10)

        tk.Label(
            top_bar, text="摄像头/麦克风进程占用检测",
            bg=BG_DARK, fg=FG_PRIMARY, font=FONT_TITLE,
        ).pack(side="left")

        tk.Button(
            top_bar, text=" 刷新进程 ",
            bg=COLOR_BTN, fg="white",
            font=FONT_SMALL, relief="flat", cursor="hand2",
            command=self._refresh_processes,
        ).pack(side="right")

        # Process list - scrolled text for simplicity
        self.proc_text = scrolledtext.ScrolledText(
            parent, bg=BG_CARD, fg=FG_PRIMARY,
            font=FONT_MONO, insertbackground=FG_PRIMARY,
            relief="flat", selectbackground=COLOR_BTN,
        )
        self.proc_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.proc_text.insert("end", "点击「刷新进程」查看当前设备占用情况...\n")
        self.proc_text.config(state="disabled")

        # Kill process frame
        kill_frame = tk.Frame(parent, bg=BG_DARK)
        kill_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(
            kill_frame, text="结束进程 PID:",
            bg=BG_DARK, fg=FG_SECONDARY, font=FONT_SMALL,
        ).pack(side="left")

        self.pid_entry = tk.Entry(
            kill_frame, bg=BG_CARD, fg=FG_PRIMARY,
            font=FONT_MONO, insertbackground=FG_PRIMARY,
            relief="flat", width=10,
        )
        self.pid_entry.pack(side="left", padx=5)

        tk.Button(
            kill_frame, text=" 结束进程 ",
            bg=COLOR_BTN_DANGER, fg="white",
            font=FONT_SMALL, relief="flat", cursor="hand2",
            command=self._kill_process,
        ).pack(side="left", padx=5)

    def _build_log_tab(self, parent):
        """Build the log viewer tab."""
        top_bar = tk.Frame(parent, bg=BG_DARK)
        top_bar.pack(fill="x", padx=10, pady=10)

        tk.Label(
            top_bar, text="操作日志",
            bg=BG_DARK, fg=FG_PRIMARY, font=FONT_TITLE,
        ).pack(side="left")

        tk.Button(
            top_bar, text=" 清空日志 ",
            bg=BG_CARD, fg=FG_SECONDARY,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            command=self._clear_log,
        ).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            parent, bg=BG_CARD, fg=FG_PRIMARY,
            font=FONT_MONO, insertbackground=FG_PRIMARY,
            relief="flat", selectbackground=COLOR_BTN,
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _on_frame_configure(self, event=None):
        self.dash_canvas.configure(scrollregion=self.dash_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.dash_canvas.itemconfig(self.canvas_window, width=event.width)

    def _update_time(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=now)
        self.root.after(1000, self._update_time)

    # ── Scanning & Detection ──────────────────────────────────────────────

    def _initial_scan(self):
        logger.info("启动初始设备扫描...")
        self._scan_devices()
        # Start tray icon
        self.tray.start()

    def _refresh(self):
        self.refresh_btn.config(state="disabled", text="扫描中...")
        self.bottom_status.config(text="正在扫描设备状态...")
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_devices(self):
        """Run detection in background thread."""
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        """Background scan of all detectors."""
        results = {}
        for detector_cls in ALL_DETECTORS:
            try:
                info = detector_cls.detect()
                results[info["key"]] = info
            except Exception as e:
                results[detector_cls.key] = {
                    "name": detector_cls.name,
                    "key": detector_cls.key,
                    "icon": getattr(detector_cls, "icon", ""),
                    "status": "warning",
                    "description": f"检测出错: {e}",
                    "enabled": False,
                    "exists": False,
                    "details": [str(e)],
                    "can_disable": False,
                }

        self.device_data = results
        self.root.after(0, lambda: self._update_ui(results))

    def _update_ui(self, results):
        """Update UI with scan results (called on main thread)."""
        active_count = 0
        active_names = []

        for key, info in results.items():
            if key not in self.device_rows:
                row = DeviceRow(
                    self.devices_frame, info,
                    toggle_callback=self._toggle_device,
                )
                row.pack(fill="x", padx=5, pady=2)
                self.device_rows[key] = row
            else:
                self.device_rows[key].update_status(info)
                self.device_rows[key].enable_toggle()

            if info.get("status") in ("active", "warning") and info.get("enabled"):
                active_count += 1
                active_names.append(info["name"])

        # Update status
        if active_count == 0:
            self.status_label.config(
                text="所有隐私设备已关闭  -  系统安全",
                fg=COLOR_SAFE,
            )
        else:
            self.status_label.config(
                text=f"当前共 {active_count} 个设备/功能处于活跃状态",
                fg=COLOR_ACTIVE if active_count > 3 else COLOR_WARNING,
            )

        self.refresh_btn.config(state="normal", text=" 刷新 ")
        now = datetime.now().strftime("%H:%M:%S")
        self.bottom_status.config(text=f"上次扫描: {now}")

        # Update tray
        self.tray.update_status(active_count, active_names)

        # Check for new camera/mic access and notify
        current_active = set()
        for key in ("camera", "microphone"):
            info = results.get(key, {})
            if info.get("status") == "active":
                current_active.add(key)

        new_active = current_active - self._prev_active
        if new_active and self.monitoring:
            for key in new_active:
                info = results.get(key, {})
                self.tray.notify(
                    "隐私警告",
                    f"{info.get('name', key)} {info.get('description', '被访问')}",
                )
        self._prev_active = current_active

    # ── Device Toggle ─────────────────────────────────────────────────────

    def _toggle_device(self, key, enable=False):
        def _do():
            action = "启用" if enable else "禁用"
            logger.info(f"用户操作: {action} {key}")
            ok, msg = PrivacyControls.toggle(key, enable=enable)
            logger.info(f"操作结果: {msg}")
            # Rescan after toggle
            self._scan_thread()

        threading.Thread(target=_do, daemon=True).start()

    # ── Disable All ───────────────────────────────────────────────────────

    def _disable_all(self):
        if not messagebox.askokcancel(
            "确认操作",
            "确定要一键禁用所有隐私相关设备和功能吗?\n\n"
            "这将禁用:\n"
            "- 摄像头、麦克风\n"
            "- 定位服务\n"
            "- 蓝牙、WiFi\n"
            "- 传感器服务\n"
            "- 远程桌面\n"
            "- 诊断数据 (设为最低)\n"
            "- 广告 ID\n"
            "- 剪贴板云同步\n\n"
            "确认继续?",
            parent=self.root,
        ):
            return

        self.disable_all_btn.config(state="disabled", text="正在禁用...")
        logger.info("用户确认: 执行一键禁用所有")

        def _do():
            results = PrivacyControls.disable_all()
            success = sum(1 for _, ok, _ in results if ok)
            total = len(results)
            logger.info(f"一键禁用完成: {success}/{total} 项成功")

            # Rescan
            self._scan_thread()

            self.root.after(0, lambda: self._disable_all_done(results))

        threading.Thread(target=_do, daemon=True).start()

    def _disable_all_done(self, results):
        self.disable_all_btn.config(
            state="normal", text="  一键禁用所有隐私设备  "
        )

        report = "一键禁用操作结果:\n\n"
        for key, ok, msg in results:
            icon = "OK" if ok else "FAIL"
            report += f"  [{icon}] {key}: {msg}\n"

        messagebox.showinfo("操作完成", report, parent=self.root)

    # ── Monitor ───────────────────────────────────────────────────────────

    def _toggle_monitor(self):
        if self.monitoring:
            self.monitoring = False
            self.monitor_btn.config(text=" 开启实时监控 ", bg="#2e7d32")
            self.monitor_status.config(text="监控: 关闭", fg=FG_DIM)
            logger.info("实时监控已关闭")
        else:
            self.monitoring = True
            self.monitor_btn.config(text=" 停止监控 ", bg=COLOR_BTN_DANGER)
            self.monitor_status.config(
                text=f"监控: 运行中 (每{self.monitor_interval}秒刷新)",
                fg=COLOR_SAFE,
            )
            logger.info(f"实时监控已开启, 间隔 {self.monitor_interval} 秒")
            self._monitor_loop()

    def _monitor_loop(self):
        if not self.monitoring:
            return
        self._scan_devices()
        self.root.after(self.monitor_interval * 1000, self._monitor_loop)

    # ── Process View ──────────────────────────────────────────────────────

    def _refresh_processes(self):
        def _do():
            occupation = ProcessDetector.get_all_occupation()
            self.root.after(0, lambda: self._show_processes(occupation))

        threading.Thread(target=_do, daemon=True).start()

    def _show_processes(self, occupation):
        self.proc_text.config(state="normal")
        self.proc_text.delete("1.0", "end")

        self.proc_text.insert("end", "=" * 60 + "\n")
        self.proc_text.insert("end", "  摄像头进程占用\n")
        self.proc_text.insert("end", "=" * 60 + "\n\n")

        cam_active = occupation["camera_active"]
        if cam_active:
            for p in cam_active:
                self._insert_proc_info(p)
        else:
            self.proc_text.insert("end", "  当前无进程占用摄像头\n")

        # Show all recent camera access
        cam_all = [p for p in occupation["camera"] if not p["in_use"]]
        if cam_all:
            self.proc_text.insert("end", "\n  最近访问过的应用:\n")
            for p in cam_all[:5]:
                self.proc_text.insert("end", f"    - {p['app']}\n")

        self.proc_text.insert("end", "\n" + "=" * 60 + "\n")
        self.proc_text.insert("end", "  麦克风进程占用\n")
        self.proc_text.insert("end", "=" * 60 + "\n\n")

        mic_active = occupation["mic_active"]
        if mic_active:
            for p in mic_active:
                self._insert_proc_info(p)
        else:
            self.proc_text.insert("end", "  当前无进程占用麦克风\n")

        mic_all = [p for p in occupation["microphone"] if not p["in_use"]]
        if mic_all:
            self.proc_text.insert("end", "\n  最近访问过的应用:\n")
            for p in mic_all[:5]:
                self.proc_text.insert("end", f"    - {p['app']}\n")

        self.proc_text.insert("end", "\n" + "-" * 60 + "\n")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.proc_text.insert("end", f"  扫描时间: {now}\n")
        self.proc_text.insert(
            "end", "  提示: 在下方输入 PID 可结束指定进程\n"
        )

        self.proc_text.config(state="disabled")

    def _insert_proc_info(self, p):
        self.proc_text.insert("end", f"  进程名: {p['app']}\n")
        if p.get("pid"):
            self.proc_text.insert("end", f"  PID:    {p['pid']}\n")
        self.proc_text.insert("end", f"  路径:   {p.get('full_path', '未知')}\n")
        if p.get("start_time") and p["start_time"] > 0:
            try:
                st = datetime.fromtimestamp(p["start_time"])
                self.proc_text.insert(
                    "end", f"  启动:   {st:%Y-%m-%d %H:%M:%S}\n"
                )
            except (ValueError, OSError):
                pass
        self.proc_text.insert("end", "  状态:   [正在使用]\n\n")

    def _kill_process(self):
        pid_str = self.pid_entry.get().strip()
        if not pid_str:
            messagebox.showwarning("提示", "请输入进程 PID", parent=self.root)
            return

        try:
            pid = int(pid_str)
        except ValueError:
            messagebox.showerror("错误", "PID 必须是数字", parent=self.root)
            return

        if not messagebox.askokcancel(
            "确认", f"确定要结束进程 PID={pid} 吗?", parent=self.root
        ):
            return

        ok, msg = ProcessDetector.kill_process(pid)
        logger.info(f"结束进程: {msg}")

        if ok:
            messagebox.showinfo("成功", msg, parent=self.root)
            self.pid_entry.delete(0, "end")
            self._refresh_processes()
        else:
            messagebox.showerror("失败", msg, parent=self.root)

    # ── Log View ──────────────────────────────────────────────────────────

    def append_log(self, message):
        """Append a log message to the log text widget."""
        try:
            self.log_text.config(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except Exception:
            pass

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ── Window Management ─────────────────────────────────────────────────

    def _on_close(self):
        if self.monitoring:
            # Minimize to tray
            self.root.withdraw()
            self.tray.notify("隐私卫士", "已最小化到系统托盘, 监控继续运行")
        else:
            self._quit_app()

    def _show_window(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _quit_app(self):
        self.monitoring = False
        self.tray.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        logger.info("Windows 隐私卫士启动")
        self.root.mainloop()


class UILogHandler(logging.Handler):
    """Custom logging handler that sends log records to the UI."""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def emit(self, record):
        try:
            msg = self.format(record)
            self.app.root.after(0, lambda m=msg: self.app.append_log(m))
        except Exception:
            pass

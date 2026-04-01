"""System tray icon with pystray."""

import threading
import logging

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

logger = logging.getLogger("PrivacyGuard")


def _create_icon_image(color="green"):
    """Create a simple colored circle icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    colors = {
        "green": (0, 200, 80),
        "red": (220, 50, 50),
        "yellow": (230, 180, 30),
    }
    fill = colors.get(color, colors["green"])

    # Draw filled circle with border
    draw.ellipse([4, 4, size - 4, size - 4], fill=fill, outline=(255, 255, 255), width=2)

    # Draw a shield shape in center
    cx, cy = size // 2, size // 2
    shield_points = [
        (cx, cy - 14),
        (cx + 12, cy - 6),
        (cx + 10, cy + 8),
        (cx, cy + 16),
        (cx - 10, cy + 8),
        (cx - 12, cy - 6),
    ]
    draw.polygon(shield_points, fill=(255, 255, 255, 180))

    return img


class TrayIcon:
    """System tray icon manager."""

    def __init__(self, show_callback=None, quit_callback=None):
        self.show_callback = show_callback
        self.quit_callback = quit_callback
        self.icon = None
        self._thread = None
        self._current_color = "green"

    def start(self):
        if not HAS_TRAY:
            logger.warning("pystray/Pillow 未安装, 系统托盘不可用")
            return

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", self._on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("状态: 安全", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._on_quit),
        )

        self.icon = pystray.Icon(
            "PrivacyGuard",
            _create_icon_image("green"),
            "隐私卫士 - 全部安全",
            menu,
        )

        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def update_status(self, active_count, device_names=None):
        """Update tray icon color and tooltip based on active device count."""
        if not self.icon:
            return

        if active_count == 0:
            color = "green"
            tooltip = "隐私卫士 - 全部安全"
        else:
            color = "red"
            names = ", ".join(device_names[:3]) if device_names else ""
            tooltip = f"隐私卫士 - {active_count} 个设备活跃: {names}"

        if color != self._current_color:
            self._current_color = color
            try:
                self.icon.icon = _create_icon_image(color)
                self.icon.title = tooltip
            except Exception:
                pass

    def notify(self, title, message):
        """Show a balloon notification."""
        if self.icon:
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def _on_show(self, icon=None, item=None):
        if self.show_callback:
            self.show_callback()

    def _on_quit(self, icon=None, item=None):
        if self.quit_callback:
            self.quit_callback()

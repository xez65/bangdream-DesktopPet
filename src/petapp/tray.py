"""System tray. The tray is the only way back from click-through mode, so it mirrors the menu."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

APP_NAME = "\u4e30\u5ddd\u7965\u5b50\u684c\u5ba0\u6a21\u62df\u5668"
# 丰川祥子桌宠模拟器. Single source for the display name; build_exe.py's SHIP_NAME must match it.


def build_tray(win, icon: QIcon | None = None) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(icon or QIcon(), win)
    tray.setToolTip(APP_NAME)
    m = QMenu(win)
    show = m.addAction("\u663e\u793a / \u9690\u85cf")          # 显示 / 隐藏
    show.triggered.connect(win.toggle_visible)
    m.addSeparator()
    through = m.addAction("\u53d6\u6d88\u9f20\u6807\u7a7f\u900f")  # 取消鼠标穿透
    through.setCheckable(True)
    through.setChecked(win.settings.click_through)
    through.toggled.connect(win.set_click_through_enabled)
    win.tray_through_action = through
    pause = m.addAction("\u6682\u505c\u81ea\u4e3b\u884c\u52a8")     # 暂停自主行动
    pause.setCheckable(True)
    pause.setChecked(win.settings.paused)
    pause.toggled.connect(win.set_paused)
    m.addSeparator()
    m.addAction("\u6253\u5f00\u83dc\u5355").triggered.connect(win.show_menu_at_cursor)
    quit_ = m.addAction("\u9000\u51fa")                          # 退出
    quit_.triggered.connect(win.quit_app)
    tray.setContextMenu(m)
    tray.activated.connect(lambda reason: win.toggle_visible()
                           if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()
    return tray

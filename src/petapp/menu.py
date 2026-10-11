"""Right-click menu (spec section 6.3). Every entry maps to a method on PetWindow."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu
from petcore import clip_manifest as cm

SEDENTARY_CHOICES = (30, 45, 60, 90)
SCALE_CHOICES = (150, 220, 300)


def build_menu(win) -> QMenu:
    m = QMenu(win)
    m.setObjectName("petMenu")

    actions = cm.CLIPS
    play = m.addMenu("\u52a8\u4f5c")          # 动作
    for c in actions:
        act = QAction(f"{c.label}  {c.slug}", m)
        act.triggered.connect(lambda _=False, s=c.slug: win.play_clip(s))
        play.addAction(act)

    feed = m.addMenu("\u5582\u98df")          # 喂食
    for key, label in (("tea", "\u8336"), ("coffee", "\u5496\u5561"),
                       ("dessert", "\u751c\u70b9"), ("bento", "\u4fbf\u5f53")):
        act = QAction(label, m)
        act.triggered.connect(lambda _=False, k=key: win.feed(k))
        feed.addAction(act)

    size = m.addMenu("\u5927\u5c0f")          # 大小
    group = QActionGroup(size)
    for px in SCALE_CHOICES:
        act = QAction(f"{px} px", m)
        act.setCheckable(True)
        act.setChecked(px == win.pet_h)
        act.triggered.connect(lambda _=False, p=px: win.set_scale(p))
        group.addAction(act)
        size.addAction(act)

    m.addSeparator()
    pom = m.addMenu("\u756a\u8304\u949f")     # 番茄钟
    start = QAction("\u5f00\u59cb", m)
    start.triggered.connect(win.start_pomodoro)
    stop = QAction("\u505c\u6b62", m)
    stop.triggered.connect(win.stop_pomodoro)
    status = QAction("\u72b6\u6001\uff1a\u672a\u5f00\u542f", m)   # 状态：未开启
    status.setEnabled(False)
    pom.addAction(start)
    pom.addAction(stop)
    pom.addSeparator()
    pom.addAction(status)
    win.pomodoro_status_action = status

    chime = QAction("\u6574\u70b9\u62a5\u65f6", m)               # 整点报时
    chime.setCheckable(True)
    chime.setChecked(win.settings.chime_enabled)
    chime.toggled.connect(win.set_chime_enabled)
    m.addAction(chime)

    sed = m.addMenu("\u4e45\u5750\u63d0\u9192")                 # 久坐提醒
    sed_on = QAction("\u5f00\u542f", m)
    sed_on.setCheckable(True)
    sed_on.setChecked(win.settings.sedentary_enabled)
    sed_on.toggled.connect(win.set_sedentary_enabled)
    sed.addAction(sed_on)
    sed.addSeparator()
    grp = QActionGroup(sed)
    for minutes in SEDENTARY_CHOICES:
        act = QAction(f"\u6bcf {minutes} \u5206\u949f", m)      # 每 N 分钟
        act.setCheckable(True)
        act.setChecked(minutes == win.settings.sedentary_min)
        act.triggered.connect(lambda _=False, v=minutes: win.set_sedentary_interval(v))
        grp.addAction(act)
        sed.addAction(act)

    behav = m.addMenu("\u884c\u4e3a")                           # 行为
    pause = QAction("\u6682\u505c\u81ea\u4e3b\u884c\u52a8", m)  # 暂停自主行动
    pause.setCheckable(True)
    pause.setChecked(win.settings.paused)
    pause.toggled.connect(win.set_paused)
    behav.addAction(pause)
    auto = QAction("\u6062\u590d\u81ea\u4e3b\u884c\u52a8")      # 恢复自主行动
    auto.triggered.connect(win.resume_autonomy)
    behav.addAction(auto)

    m.addSeparator()
    through = QAction("\u9f20\u6807\u7a7f\u900f\uff08\u5f00\u542f\u540e\u53ea\u80fd\u4ece\u6258\u76d8\u5173\u95ed\uff09", m)
    # 鼠标穿透（开启后只能从托盘关闭）
    through.setCheckable(True)
    through.setChecked(win.settings.click_through)
    through.toggled.connect(win.set_click_through_enabled)
    m.addAction(through)

    top = QAction("\u59cb\u7ec8\u7f6e\u9876", m)                # 始终置顶
    top.setCheckable(True)
    top.setChecked(win.settings.topmost)
    top.toggled.connect(win.set_topmost)
    m.addAction(top)

    bars = QAction("\u663e\u793a\u72b6\u6001\u9762\u677f", m)   # 显示状态面板
    bars.setCheckable(True)
    bars.toggled.connect(win.set_show_stats)
    m.addAction(bars)

    m.addSeparator()
    reset = QAction("\u91cd\u7f6e\u4f4d\u7f6e", m)              # 重置位置
    reset.triggered.connect(win.reset_position)
    m.addAction(reset)
    move = QAction("\u79fb\u5230\u4e0b\u4e2a\u663e\u793a\u5668", m)  # 移到下个显示器
    move.triggered.connect(win.next_screen)
    m.addAction(move)
    hide = QAction("\u9690\u85cf\u5230\u6258\u76d8", m)         # 隐藏到托盘
    hide.triggered.connect(win.hide_to_tray)
    m.addAction(hide)
    quit_ = QAction("\u9000\u51fa", m)                          # 退出
    quit_.triggered.connect(win.quit_app)
    m.addAction(quit_)
    return m

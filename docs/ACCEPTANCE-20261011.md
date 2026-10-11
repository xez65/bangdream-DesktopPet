# 凤川祥模拟器 · 验收记录 2026-10-11

环境：Windows 11 10.0.26200 x64，单屏 2560×1440，Qt DPR 1.0，Python 3.12.10 venv，
PySide6-Essentials 6.12.0，Pillow 12.3.0，PyInstaller 6.22.3。
所有数字来自本机实跑，命令与产物同目录可复核；未测的明确写未测。

## 交付物

| 项 | 值 |
|---|---|
| 程序 | `DesktopPet/dist/凤川祥模拟器.exe`（文件名按码点核对为 U+51E4 U+5DDD **U+7965** 模拟器） |
| 体积 | 113,498,968 B（约 108.2 MiB） |
| sha256 | `eb56bcd02e584c8bb5f9f20df1b0faaab17788c2bf289b6194a42f064e1e59db` |
| 内嵌资源 | 2,166 帧 / 66,084,806 B，`clips.json` sha256 `2b526ca9…`，源索引 sha256 `f7d8f242…` |
| 构建时 commit | `509079b`（含手动钉住修复） |
| 源码 | `DesktopPet/`，`requirements.txt` 四个依赖钉版本 |

## 门槛结果

| 门槛 | 目标 | 实测 | 判定 |
|---|---|---|---|
| 帧数与包体 | 2,166 帧、58–70 MB | 2,166 帧、63.0 MB（`clips.json` 记 66,084,806 B 含 8px pad 后重编） | 达标 |
| 构建可复现 | 两次独立并行构建逐文件一致 | 2,166 个 webp 全部 sha256 相同 | 达标 |
| 裁剪框安全 | 无帧越界 | 逐帧全扫 2,166 帧，越界 0，触边 0 | 达标 |
| 待机接缝 | 首尾差 <1 | 0.035 | 达标 |
| 自动化测试 | 全绿 | 106 passed（含 25 项 Qt 壳 offscreen 测试） | 达标 |
| 帧解码 | 逐 clip 前 5 帧非空 | 17 组 × 5 = 85 帧，bad=0 | 达标 |
| tick p95 | ≤ 8 ms | 6.68 ms（exe，25 s 窗口 540 tick） | 达标 |
| tick 最大值 | 未设门槛 | 51 ms 常态；一次观测到 **2,067 ms** 离群（onefile 解包期撞磁盘） | 记录 |
| 空闲 CPU | ≤ 5% | 外部 `GetProcessTimes` 25 s 差分 **0.06%**；进程自报生命周期 **1.16%**（含启动） | 达标 |
| RSS | ≤ 350 MB | **82.6 MB** 峰值（25 次采样） | 达标 |
| onefile 冷启动 | ≤ 8 s | `--once` 全程 6.08 s（含应用内 2.5 s 展示与 2.5 s 等待），退出码 0 | 达标（口径见下） |
| 独立性 | 不依赖本机 Python | 从 `%TEMP%` 空目录启动，PATH 已剔除 Python 条目（`python_left_on_path: false`），退出码 0 且写出 3 张证据图 | 达标 |
| 透明边缘 | 无白边 | 11:13 真机桌面截图 + 3× 放大：发丝与衣缘与动态壁纸正确混合，无白边 | 达标 |

冷启动口径说明：6.08 s 是"启动进程 → `--once` 跑完退出"的总时长，不是"到首帧"的时间。
首帧时间未单独埋点，这是本次验收的一个已知缺口，不做数字美化。

## 交互与功能实测

驱动方式：`QLocalServer` 控制通道（仅 `DESKTOPPET_DEV=1` 受理），对**已运行的 exe** 下发命令，
不触碰内部实现。12 个场景由 `QWidget.grab()` 自渲染出证，逐张 sha256 与体积互不相同：

| 场景 | 产物 | 体积 |
|---|---|---|
| 待机 / 微笑 / 生气 / 思考 / 挥手 / 惊讶 | `01`–`06` | 22.3–24.2 KB |
| 气泡（"别闹。"） | `07_bubble.png` | 21.2 KB |
| 喂食（"谢谢，正好饿了。"） | `08_feed.png` | 23.0 KB |
| 番茄钟安静态 | `09_quiet.png` | 22.5 KB |
| 状态面板三条数值条 | `10_stats_panel.png` | 23.6 KB |
| 300 / 150 缩放 | `11`、`12` | 68.3 / 24.1 KB |

菜单与托盘由测试逐个 `trigger()`，25+ 项动作全部可调用不抛；鼠标穿透经 ctypes 设
`WS_EX_TRANSPARENT` 后 `WindowFromPoint` 命中测试确认穿透（Qt 自带的
`WindowTransparentForInput` 实测**不**生效）；`GetLastInputInfo` 两次采样 157,953→158,343 ms 正常递增；
拖拽→被拎→松手→重力→落地回任务栏在 offscreen 测试中通过；存档写 `%APPDATA%\DesktopPetSakiko\`
并能在重开后读回，坏档走 `.bad-<时间戳>` 保留证据。

## 未覆盖 / 待用户确认

1. **手感未做人工确认**。拎起是否跟手、抛掷力度、气泡时长 3.2 s、待机 8–20 s 的随机节奏，
   这些需要眼睛判，自动化只能证明状态机按预期走。
2. **首帧耗时未埋点**，因此"冷启动 ≤ 8 s"目前只有全程时长支撑。
3. **图标裁方选择**。默认用了 `subject`（横向下按主体中心裁、纵向占满照片区），
   `assets/icon_candidate_subject.png` 与 `icon_candidate_centred.png` 两张候选已落盘，
   换一张只需 `tools/make_icon.py --crop centred` 后重打包。
4. **会话锁定时的测量陷阱**（记录以免日后误判）：屏幕熄灭/锁屏后桌面截图全黑
   （11:30 那轮 10 张全 15 KB 同一内容），且进程工作集被裁剪到 4.9 MB、CPU 读 0，
   那批数字全部作废；本文所有性能数都在屏幕点亮、会话活跃时重测。
5. 开机自启与系统监控按用户澄清轮的决定**未做**，不在缺口内。
6. **与计划的一处有意偏离**：计划里列了 `tools/verify_assets.py`，实际没有这个文件。
   它的职责（帧数、逐帧越界、接缝、包体、源索引回指）全部落在 `tests/test_assets.py` 里，
   再用一个 CLI 包一层只会让同一套判据出现两个入口。要手工核验直接跑
   `pytest tests/test_assets.py -q` 或 `tools/build_clips.py --dry-run`。
7. 构建续跑判据已单独复核：配置未变时重跑打印 `0 built, 17 reused, 0 failed in 0.0s`。

## 复现命令

```
cd DesktopPet
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe tools\build_clips.py --dry-run --jobs 8
.venv\Scripts\python.exe tools\build_clips.py --jobs 8
.venv\Scripts\python.exe tools\make_icon.py
.venv\Scripts\python.exe tools\build_exe.py --launch
.venv\Scripts\python.exe tools\accept_shots.py --exe --out dev\shots-exe
.venv\Scripts\python.exe tools\measure_perf.py --exe --seconds 25
```

## 缺陷修复：菜单选动作被自主状态机抢走（2026-10-11 用户报）

现象：右键让桌宠「待机」，它演一下就换成别的动作。

复现与定位（headless 逐项点菜单）证明菜单路由本身没错，17 项全部渲染到请求的那一组；
真正的问题在行为层，两条都是设计缺陷：

1. `BehaviorCore.request()` 把手动选择塞进 `STATE_REACT`，而 REACT 的收尾判据是
   `_clip_elapsed >= duration`。于是标着 `loop` 的动作（思考 4.33 s、向左走、被拎、认真）
   也只演一遍就被收回，实测 4.25 s 后被 `sakiko_idle01` 顶掉。
2. 一个周期跑完立刻交还随机状态机。待机一轮 7 s，7 s 后有五成概率掷出走路的或
   随机小动作，用户看到的就是"我让它待机，它反而做了别的"。

修法：手动选择进入 `STATE_MANUAL` 钉住态。循环动作一直演到用户下一次操作为止；
一次性动作演完回到钉住的待机；整点报时与久坐提醒演完仍回到被钉住的那组；
直接操作（戳、抚摸、喂食、拎起、开始番茄钟）解除钉住并把自主权还给状态机。
菜单「行为」里新增「恢复自主行动」作为显式出口。

顺带修掉一个由本次排查暴露的通道缺陷：`InstanceGuard.acquire()` 在 `listen()` 失败
且探测不到活实例（被 kill 的实例留下陈旧命名管道）时，会带着桌宠跑起来但整生命周期
都没有控制通道。改为探测失败后 `removeServer` 再监听一次。

对打包 exe 的修复验证（`DESKTOPPET_DEV=1`，每 3 秒问一次当前动作，共 30 秒）：
选「思考」后 held 集合 = {`sakiko_thinking01`}，未再被顶掉；发 `resume` 后随机机恢复
（观测到 `sakiko_idle01` 与 `sakiko_nod01`）；`quit` 退出码 0。
回归测试 7 项（钉住保持、一次性回落、提醒后回钉、戳解除、恢复自主、拎起不复活钉住、
走路钉住不产生位移）并入 `tests/test_behavior.py`，全套 113 项通过。

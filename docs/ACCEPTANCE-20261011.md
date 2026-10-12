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

## 2026-10-12 追加一：更名

用户把产品中文名定为「丰川祥子桌宠模拟器」（U+4E30 U+5DDD U+7965 U+5B50 U+684C U+5BA0
U+6A21 U+62DF U+5668）。本文上面 10-11 那轮按当时事实保留，不回改。

- 改动落在 `tray.APP_NAME`（显示名的唯一出处，托盘 tooltip 用它）、`build_exe.SHIP_NAME`
  和二次启动提示；`tests/test_scaffold.py` 新增一笔把前两处字面量钉成同一串码点，
  因为 10-11 那次码点写错已经留下过两个陈旧 exe。
- 内部标识不变：`setApplicationName`、`APP_DIRNAME`、`SERVER_NAME` 仍是 `DesktopPetSakiko`，
  所以 `%APPDATA%\DesktopPetSakiko\` 的存档和命名管道沿用，改名不会让老档变成"第一次运行"。
- 烘培目录名首字是 凤（U+51E4），角色名首字是 丰（U+4E30），两者不同，路径引用不要一起改。

## 2026-10-12 追加二：单实例是真缺陷，判据换成内核互斥量

现象：同一次登录里可以同时站起来两只桌宠，第二只照旧 show()，没有任何"已有实例"提示。

根因是实测出来的：`QLocalServer.listen()` 在 Windows 上不是独占判据。两个活进程用同一个名字
调 `listen()`，两边都返回 True、各自持有一个可用 server，谁也没看见谁；10-11 那版
"探测管道失败就 removeServer 再监听"的写法因此反而让第二个进程理直气壮地当主实例。

- `src/petapp/win32.py` 加 `acquire_named_mutex()`：`CreateMutexW` + `Local\` 前缀（会话内可见），
  `GetLastError` 用 `ctypes.WinDLL(..., use_last_error=True)` 读，避免被中间 ctypes 调用污染；
  `ERROR_ALREADY_EXISTS(183)` 判已被占。互斥量随进程由内核释放，硬杀不留尸体。
- `src/petapp/instance.py`：所有权只由互斥量决定，拿到以后才 `removeServer` + `listen`，
  管道退化为 dev 控制通道。删掉 liveness ping/pong 探测（实测真实应用里 `connected=1` 却收不到回）。
- 新增 `tests/test_instance_guard.py` + `tests/guard_child.py`（子进程是真解释器，可硬杀）：
  持有者活着 → 第二个进程 `acquire()` 必须 False 且不拥有 server/mutex；
  持有者被硬杀 → 下一个进程必须能拿到（管道方案做不到这条，因为尸体还占着名字）。
- 诊断口子 `DESKTOPPET_GUARD_DEBUG=1` 打印 GUARD/CHANNEL 两类分支，管道归属在进程列表里本来看不见。

打包 exe 的真机验证（`dist/丰川祥子桌宠模拟器.exe`，113,500,786 B，sha256 `8755c847db278ff3…`，
内嵌 `gitCommit f9eeb58`，`DESKTOPPET_DEV=1`）：

- 首实例控制通道回读 `pid` → `OK pid 10604 parent 8948`，`current` →
  `OK current sakiko_idle01 frame=0 state=idle pinned=False`
- 第二次启动：14 s 后退出码 0，首实例仍在运行，再问 `pid` 还是同一个 10604 ⇒ 没有第二只
- `quit` 之后首实例退出码 0
- 冷启动口径与 10-11 相同（`%TEMP%` 空目录、PATH 剔除 Python）：`--once` 退出码 0，全程 6.09 s，
  ticks=51 p95=7.73 ms，cache misses=50 evictions=0 failed_keys=0；首帧耗时依旧未埋点

本轮全套 `pytest -q` → 115 passed / 1 skipped（tick 门只在 `DESKTOPPET_PERF=1` 时生效）。

排查陷阱（记下来免得下次误判成代码坏了）：`DesktopPet/` 根目录留着上一轮验证起的两个
`凤川祥模拟器.exe` 进程，它们占着 `DesktopPetSakiko` 管道名但不带 `DESKTOPPET_DEV`，
于是外部命令连得上却一个字节都收不到；而且 `taskkill /IM python.exe` 抓不到它们
（进程名是中文 exe）。杀掉之后同样的探测立刻变成 `ServerNotFoundError`，通道才回到可判定状态。
根目录那个旧名 exe（113,622,678 B，10-11 11:51 构建）仍在原地，未删。

## 2026-10-12 追加三：数值面板改像素风，以及顺带挖出的两个坑

面板本身（`PetWindow._paint_stat_bars`）：浅紫纸底 #f4f1ff（alpha 226）+ 1 像素深靛 #2b2a4a 描边、
四角各抠一像素做切角；每条数值拆 8 段方块，填充段是"顶 1 像素高光 + 本色 + 底 1 像素深色收边"三层，
空格段用 #d9d4e8 加 #c4bed6；名称「饱食 / 心情 / 亲密」移到左侧独立文字列，垂直居中对齐各自行。
像素格 `px = max(2, round(pet_h/220*3))`，行高取 `max(px*5, QFontMetrics(font).height()+px)`，
字号 `min(11, max(8, round(pet_h/26)))`。真实窗口平台实测：pet_h 150/220/300 时面板底边 55/60/80，
气泡顶边恒为 88，几何不变量已进 `tests/test_app_window.py::test_stat_panel_clears_the_bubble_band`。

坑一（我自己的改名漏项）：`tools/accept_shots.py` 和 `tools/measure_perf.py` 各自还硬编码着旧产物名
`凤川祥模拟器.exe`，所以第一次 `--exe` 采集驱动的是 10-11 那个旧 exe，出图仍是旧面板。
两处已改成从 `tools/build_exe.SHIP_NAME` 派生，并纳入 `tests/test_scaffold.py` 的同名钉死断言
（现在断言覆盖 tray.APP_NAME、build_exe.SHIP_NAME、accept_shots.EXE、measure_perf.EXE_NAME 四处）。

坑二（会让整批视觉证据作废的开关）：`%APPDATA%\DesktopPetSakiko\settings.json` 里
`paused: true` 时 `PetWindow._on_tick` 只在首帧未解码时才走时间轴，于是 12 个场景全部停在
`sakiko_idle01` 第 0 帧且图片哈希完全相同；同样的状态下右键选动作也没有任何可见变化。
本轮采集改为把 `APPDATA` 指到临时目录再跑，不触碰用户存档；重跑后 12 张图哈希互不相同，
`slug` 与场景请求的动作一一对应（02→smile01、03→angry01、04→thinking01、06→surprised01、08→shame01）。
这条属于"暂停自主行动"的既有语义，不是缺陷；但用户如果看到桌宠一动不动，先查这个勾。

产物与证据：`dist/丰川祥子桌宠模拟器.exe` 113,502,651 B，sha256 `2ff4d64165614e09…`，
内嵌 `gitCommit c31cb08`；场景图在 `dev/shots-pixel/`（12 张 + `scenes_manifest.json` + `manifest.json`），
公开仓 `docs/screenshots/` 的四张已换成这一轮。全套 `pytest -q` → 116 passed / 1 skipped。

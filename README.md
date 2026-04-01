# Windows 隐私卫士 (Privacy Guard)

Windows 隐私设备监控与管理工具，实时监控并管理系统中所有隐私相关设备和功能。

## 功能特性

- **设备状态总览**：仪表盘显示 13 项隐私设备/功能的实时状态
- **一键禁用**：一键禁用所有隐私相关设备和功能
- **进程占用检测**：查看哪些进程正在使用摄像头/麦克风
- **实时监控**：后台每 30 秒自动扫描，托盘图标实时反映状态
- **系统托盘**：最小化到托盘，新设备访问时弹窗警告
- **操作日志**：所有操作记录到本地 log 文件

## 检测项目

| 设备/功能 | 检测原理 | 关键路径/命令 |
|---|---|---|
| 摄像头 | PnP 设备枚举 + ConsentStore 注册表 | `Get-PnpDevice -Class Camera`; `HKCU\...\ConsentStore\webcam` |
| 麦克风 | PnP AudioEndpoint 枚举 + ConsentStore | `Get-PnpDevice -Class AudioEndpoint`; `HKCU\...\ConsentStore\microphone` |
| 定位服务 | lfsvc 服务状态 + ConsentStore 注册表 | `sc query lfsvc`; `HKLM\...\ConsentStore\location\Value` |
| 蓝牙 | PnP Bluetooth 类设备枚举 | `Get-PnpDevice -Class Bluetooth` |
| WiFi | netsh 接口查询 | `netsh interface show interface`; `netsh wlan show interfaces` |
| USB摄像头 | PnP Camera/Image 中 USB 实例 | `Get-PnpDevice -Class Camera \| Where InstanceId -like 'USB*'` |
| 传感器服务 | Windows 服务状态查询 | `sc query SensorService / SensorDataService / SensrSvc` |
| 远程桌面 | 注册表 fDenyTSConnections | `HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\fDenyTSConnections` |
| 诊断数据 | 注册表 AllowTelemetry 值 | `HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection\AllowTelemetry` |
| Cortana | 注册表 AllowCortana + CortanaConsent | `HKLM\...\Windows Search\AllowCortana`; `HKCU\...\Search\CortanaConsent` |
| 广告 ID | 注册表 AdvertisingInfo\Enabled | `HKCU\...\AdvertisingInfo\Enabled` |
| 后台应用 | 注册表 BackgroundAccessApplications | `HKCU\...\BackgroundAccessApplications\GlobalUserDisabled` |
| 剪贴板历史 | 注册表 Clipboard 设置 | `HKCU\SOFTWARE\Microsoft\Clipboard\EnableCloudClipboard` |

### ConsentStore 注册表路径

摄像头和麦克风的进程占用通过 Windows CapabilityAccessManager 检测：

```
HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam
HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone
```

每个子键代表一个应用，包含：
- `LastUsedTimeStart`（QWORD）：上次开始使用的 FILETIME
- `LastUsedTimeStop`（QWORD）：上次停止使用的 FILETIME
- 当 `LastUsedTimeStart > 0` 且 `LastUsedTimeStop == 0` 时，表示设备正在被使用

### 控制操作原理

| 操作 | 实现方式 |
|---|---|
| 禁用摄像头/麦克风 | `Disable-PnpDevice` PowerShell cmdlet |
| 禁用蓝牙 | `Disable-PnpDevice -Class Bluetooth` |
| 禁用 WiFi | `netsh interface set interface "Wi-Fi" disable` |
| 禁用定位 | 停止 lfsvc 服务 + 设置 ConsentStore 为 "Deny" |
| 禁用 RDP | 设置 `fDenyTSConnections = 1` |
| 降低遥测 | 设置 `AllowTelemetry = 0` + 停止 DiagTrack 服务 |
| 禁用广告 ID | 设置 `AdvertisingInfo\Enabled = 0` |
| 禁用剪贴板云同步 | 设置 `EnableCloudClipboard = 0` |
| 禁用后台应用 | 设置 `GlobalUserDisabled = 1` |
| 禁用 Cortana | 设置 `AllowCortana = 0` |

## 安装

### 环境要求

- Windows 10/11
- Python 3.10+
- 管理员权限

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

程序会自动请求管理员权限（UAC 提权）。

## PyInstaller 打包

生成单文件 .exe（包含所有依赖）：

```bash
pip install pyinstaller

pyinstaller --onefile --windowed --name "PrivacyGuard" ^
    --add-data "detectors;detectors" ^
    --add-data "controls;controls" ^
    --add-data "ui;ui" ^
    --icon=NONE ^
    --uac-admin ^
    main.py
```

打包后的 exe 文件位于 `dist/PrivacyGuard.exe`。

`--uac-admin` 参数会在 exe 的 manifest 中声明需要管理员权限，运行时自动弹出 UAC 提示。

## 项目结构

```
windowsyinsi/
├── main.py                  # 入口文件 (UAC 提权)
├── requirements.txt         # Python 依赖
├── README.md                # 说明文档
├── detectors/               # 检测模块
│   ├── __init__.py          # 导出所有检测器
│   ├── hardware.py          # 硬件设备检测 (摄像头/麦克风/蓝牙/WiFi/USB/传感器)
│   ├── software.py          # 软件功能检测 (定位/RDP/遥测/Cortana/广告ID/剪贴板/后台应用)
│   └── processes.py         # 进程占用检测
├── controls/                # 控制模块
│   ├── __init__.py
│   └── actions.py           # 所有启用/禁用操作
├── ui/                      # 界面模块
│   ├── __init__.py
│   ├── app.py               # 主窗口 (仪表盘/进程/日志)
│   └── tray.py              # 系统托盘图标
└── logs/                    # 日志目录 (自动创建)
    └── privacy_guard_YYYYMMDD.log
```

## 注意事项

- 本工具需要 **管理员权限** 运行，否则无法禁用设备和修改系统设置
- 禁用摄像头/麦克风会影响所有使用这些设备的应用程序
- 禁用 WiFi 会断开当前网络连接
- 修改注册表设置可能需要重启或重新登录才能完全生效
- 建议在操作前了解每个选项的影响

## 技术栈

- Python 3.10+
- tkinter（内置 GUI）
- pystray + Pillow（系统托盘）
- winreg（内置，注册表操作）
- subprocess（系统命令调用）
- psutil（进程信息查询）
- ctypes（UAC 提权）

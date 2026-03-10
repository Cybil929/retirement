# 躺平进度条 - Windows 系统托盘退休倒计时工具

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

一个精致的 Windows 系统托盘小工具，帮你计算距离财务自由还有多久，并每月提醒你更新存款进度。

## 功能特性

- 系统托盘常驻：程序启动后只在系统托盘显示图标，无主窗口，不打扰工作
- 实时倒计时：鼠标悬停显示距离退休目标还剩多少年、月、天（精确计算，考虑闰年）
- 每月提醒：每月第一天自动弹出提醒，提示更新存款金额
- 点击通知直达：点击通知可直接打开"更新存款"窗口（需安装 win10toast-click）
- 复利计算：支持设置预期年化收益率，计算时考虑复利效应
- 配置持久化：所有设置自动保存到 config.json

## 安装方法

### 方法一：下载即用（推荐）

1. 从 [Releases](../../releases) 页面下载 `躺平进度条.exe`
2. 双击运行即可
3. 首次运行后会自动创建配置文件

### 方法二：从源码运行

```bash
# 1. 克隆或下载本仓库
# 2. 安装依赖
pip install pystray Pillow python-dateutil plyer win10toast-click

# 3. 运行
python retirement_tray.py
```

## 使用方法

### 初始设置

1. 右键点击托盘图标 → 选择"设置"
2. 填写以下信息：
   - **目标退休金额**：你计划存多少钱后退休（例如：2000000 表示 200 万）
   - **当前已存金额**：目前已有的存款
   - **每月储蓄金额**：预计每月能存下的钱
   - **预期年化收益率**（可选）：投资收益率，默认为 0
3. 点击"保存"

### 日常使用

- **查看进度**：鼠标悬停在托盘图标上
- **更新存款**：右键菜单 → "更新当前存款"
- **修改设置**：右键菜单 → "设置"
- **退出程序**：右键菜单 → "退出"

### 每月提醒

每月第一天，程序会自动弹出提醒通知：
- 如果安装了 `win10toast-click`：点击通知可直接打开更新窗口
- 如果未安装：弹窗提示，可选择是否立即更新

## 打包成 exe（开发者）

### 一键打包

双击运行 `pack.bat`，或在命令行执行：

```bash
.\pack.bat
```

打包完成后，exe 文件位于 `dist/躺平进度条.exe`

### 手动打包

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole \
    --hidden-import=pystray \
    --hidden-import=PIL \
    --hidden-import=dateutil \
    --hidden-import=plyer \
    --hidden-import=win10toast_click \
    --name="躺平进度条" \
    retirement_tray.py
```

## 计算逻辑说明

### 不考虑收益（年化收益率 = 0）

```
所需月数 = ceil((目标金额 - 当前存款) / 每月储蓄)
目标日期 = 今天 + 所需月数
```

### 考虑收益（年化收益率 > 0）

使用月复利公式逐月模拟：

```python
月利率 = 年化收益率 / 12 / 100
余额 = 当前存款
月数 = 0
while 余额 < 目标金额:
    余额 = 余额 * (1 + 月利率) + 每月储蓄
    月数 += 1
目标日期 = 今天 + 月数
```

### 剩余时间显示

使用 `dateutil.relativedelta` 精确计算两个日期之间的差值，正确处理：
- 闰年（2月29天）
- 不同月份天数（28/30/31天）
- 跨月、跨年计算

## 文件说明

```
.
├── retirement_tray.py    # 主程序源码
├── pack.bat              # 一键打包脚本
├── config.json           # 配置文件（运行时自动生成）
├── retirement_app.log    # 运行日志（自动生成）
└── README.md             # 本说明文件
```

## 依赖列表

| 依赖 | 用途 | 是否必需 |
|------|------|---------|
| pystray | 系统托盘图标 | 是 |
| Pillow | 图标生成 | 是 |
| python-dateutil | 精确日期计算 | 是 |
| tkinter | GUI界面 | 内置 |
| plyer | Windows通知 | 可选 |
| win10toast-click | 可点击的通知 | 可选（推荐） |

## 常见问题

### Q: 程序无法启动？
A: 请确保已安装所有必需依赖，或直接使用打包好的 exe 文件。

### Q: 托盘图标不显示？
A: 可能是 Windows 托盘图标被折叠到隐藏区域，点击任务栏向上的箭头查看。

### Q: 每月提醒没有弹出？
A: 请检查 Windows 通知设置是否允许该程序发送通知。

### Q: 如何修改配置？
A: 右键托盘图标 → "设置"，或直接编辑 config.json 文件。

## 开源协议

MIT License - 自由使用、修改和分发

---

祝早日财务自由！🏖️

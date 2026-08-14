# MyWhoosh FIT → Garmin Connect 上传工具

将 MyWhoosh 室内骑行导出的 FIT 文件自动增强并上传到 Garmin Connect。

## 功能

- **设备伪装** — 将 MyWhoosh FIT 中的设备信息伪装为 Garmin Edge 1040
- **运动类型修正** — 设置为骑行 + 虚拟活动（Virtual Activity）
- **强度指标计算** — 自动计算 NP（标准化功率）、IF（强度因子）、TSS（训练压力评分）
- **自动上传** — 增强完成后自动上传到 Garmin Connect
- **重复检测** — Garmin 返回 409 时自动跳过重复活动
- **批量处理** — 扫描目录下所有 .fit 文件，逐个处理上传
- **跨平台** — Windows / macOS / Linux 均支持

## 系统要求

- **Python** >= 3.8

## 安装

```bash
# 安装依赖
pip install garminconnect fit-tool

# 复制并填写配置
cp .env.example .env
# 编辑 .env 填入 Garmin 账号密码
```

## 使用

### 一次性批量处理

```bash
python3 mywhoosh2garmin.py
```

首次运行会弹出文件夹选择窗口，也可在 `.env` 中配置 `MYWHOOSH_FIT_DIR` 跳过选择。

### 自动监视目录（推荐）

```bash
# 可选：安装 watchdog 获得即时检测（否则自动回退到 5s 轮询）
pip install watchdog

python3 watch_and_sync.py
```

`watch_and_sync.py` 会持续监视 `MYWHOOSH_FIT_DIR`，每当检测到新 `.fit` 文件时自动增强并上传到 Garmin Connect。按 `Ctrl+C` 停止。

> **注意：** 使用此模式必须在 `.env` 中设置 `MYWHOOSH_FIT_DIR`，无法通过弹窗选择。

### MyWhoosh FIT 文件位置

| 系统 | 路径 |
|------|------|
| **macOS** | `~/Library/Containers/com.whoosh.whooshgame/Data/Library/Application Support/Epic/MyWhoosh/Content/Data` |
| **Windows** | `C:\Users\<用户名>\AppData\Local\Packages\MyWhooshTechnologyService.*\LocalCache\Local\MyWhoosh\Content\Data` |

## 项目结构

```
mywhooshfit_to_garminfit/
├── mywhoosh2garmin.py       ← 一次性批量处理
├── watch_and_sync.py        ← 目录监视器（自动增强+上传）
├── enhance_fit_cli.py       ← FIT 增强脚本
├── .env                     ← 配置文件（含账号密码，已 gitignore）
├── .env.example             ← 配置模板
└── README.md
```

## 常见问题

### Garmin 登录失败

1. 检查网络是否能访问 `connect.garmin.com`
2. 确认账号密码正确
3. Garmin 有登录频率限制，失败后等几分钟再试

### FIT 增强失败

1. 确认 fit-tool 已安装：`python3 -c "import fit_tool"`
2. 检查 FIT 文件是否完整
3. 查看终端输出的错误信息

### 上传显示重复

Garmin Connect 已存在相同活动，脚本会自动跳过，不报错。

## 致谢

- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) — Garmin Connect API Python 客户端
- [fit-tool](https://pypi.org/project/fit-tool/) — Python FIT 文件处理库

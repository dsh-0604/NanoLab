# NanoCode 电子实验室 (NanoLab)

本机硬件仿真程序，原生 PySide6（不是网页）。虚拟开发板 + 配件 + 电路物理仿真，
与 [NanoCode](https://github.com/dsh-0604/NanoCode) IDE 组成双软件生态：
在 NanoCode 写 ESP32/C++ 代码 → 一键送到实验室 → 在虚拟硬件上跑起来。

## 运行

```bash
pip install PySide6
python 启动.py
```

桌面版双击 `NanoCode电子实验室.exe`。

## 桥接接口

HTTP 服务 `127.0.0.1:8765`（随窗口启停）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/health | 健康检查 |
| POST | /api/run | 推送代码 `{code, board, filename}` |
| POST | /api/stop | 停止仿真 |
| POST | /api/serial | 串口发送 `{text}` |
| GET | /api/output?since=N | 取串口输出 |
| POST | /api/arrange | 自动排布配件 |

## 生态连接

- NanoCode 工具栏「虚拟实验室」按钮 → 一键送代码
- 自动监听 `D:\PlatformIO\c3_blink\src`，NanoCode 保存即仿真（零改造）

## 特性

- 52 个配件 / 12 块开发板（毫米真实尺寸、排针 2.54mm）
- 电路物理引擎：串联/并联/短路、电阻限流、LED 烧毁（默认 100% 必烧，可调）
- 9 个演示场景
- 紧凑模式 / 并排窗口 / 烧毁概率记忆

## 目录

- `nanolab/` 源码（data 配件板子库 / engine 物理引擎 / ui 界面）
- `docs/` 改进记录与任务书

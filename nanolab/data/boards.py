# -*- coding: utf-8 -*-
"""开发板几何数据（单位：毫米，按真实尺寸；引脚按 2.54mm 排针间距摆放）"""

from __future__ import annotations

PITCH = 2.54


def _pin(pid, label, kind, caps=None, side="left", x=0.0, y=0.0, v=5.0):
    return {
        "id": pid, "label": label, "kind": kind, "caps": caps or [kind],
        "side": side, "x": round(x, 2), "y": round(y, 2), "voltage": v,
    }


def _row(items, side, x, y0, step=PITCH, usable=None):
    """沿一条边排针：优先 2.54mm；板子不够长就按可用长度压缩，绝不出板边"""
    if not items:
        return []
    if usable is not None and len(items) > 1:
        step = min(step, max(1.3, usable / (len(items) - 1)))
    out = []
    for i, it in enumerate(items):
        pid, label, kind = it[0], it[1], it[2]
        caps = it[3] if len(it) > 3 else [kind]
        v = it[4] if len(it) > 4 else 5.0
        out.append(_pin(pid, label, kind, caps, side, x, y0 + i * step, v))
    return out


def board(bid, name, mcu, w, h, left, right, *, top=(), bottom=(), color="#1b2430",
          caps=None, note="", usb=("top", 0.42), led=None, family="", logic=3.3):
    """left/right 为 (id, label, kind[, caps[, voltage]]) 元组序列，自上而下排布"""
    pins = []
    # 左侧：从 y0 开始向下
    pins += _row(left, "left", 2.2, 5.0, usable=max(6.0, h - 10.0))
    # 右侧：从底部往上（更贴近实物：丝印从下往上数）——这里仍然自上而下，
    # 但把顺序反向，使得 GND/3V3 在顶部附近
    pins += _row(right, "right", w - 2.2, 5.0, usable=max(6.0, h - 10.0))
    if top:
        start = max(3.0, (w - len(top) * PITCH) / 2 + PITCH / 2)
        for i, it in enumerate(top):
            pid, label, kind = it[0], it[1], it[2]
            caps_i = it[3] if len(it) > 3 else [kind]
            pins.append(_pin(pid, label, kind, caps_i, "top", start + i * PITCH, 2.2))
    if bottom:
        start = max(3.0, (w - len(bottom) * PITCH) / 2 + PITCH / 2)
        for i, it in enumerate(bottom):
            pid, label, kind = it[0], it[1], it[2]
            caps_i = it[3] if len(it) > 3 else [kind]
            pins.append(_pin(pid, label, kind, caps_i, "bottom", start + i * PITCH, h - 2.2))

    feats = [{"type": "usb", "side": usb[0], "pos": usb[1], "w": 9.0, "h": 5.2}]
    feats.append({"type": "module", "x": w * 0.30, "y": h * 0.34,
                  "w": max(10.0, w * 0.34), "h": max(7.0, h * 0.30), "label": mcu})
    if led:
        feats.append({"type": "led", "x": led[0], "y": led[1], "label": "LED"})
    feats.append({"type": "reset", "x": w - 6.5, "y": h - 6.0, "label": "RST"})

    return {
        "id": bid, "name": name, "mcu": mcu, "family": family,
        "w": float(w), "h": float(h), "color": color,
        "logic": logic, "pins": pins, "features": feats, "note": note,
        "capabilities": caps or {"analog_bits": 12, "builtin_led": None},
    }


BOARDS = {}


def add(b):
    BOARDS[b["id"]] = b


# ---------------------------------------------------------------- ESP32-C3
add(board(
    "esp32-c3-devkitm-1", "ESP32-C3-DevKitM-1", "ESP32-C3-MINI-1", 25.5, 62.5,
    left=[("5V", "5V", "power", ["power"], 5),
          ("GND1", "G", "gnd", ["gnd"], 0),
          ("3V3", "3V3", "power", ["power"], 3.3),
          ("GPIO2", "2", "digital"),
          ("GPIO3", "3", "digital"),
          ("GPIO4", "4", "digital", ["digital", "adc"]),
          ("GPIO5", "5", "digital", ["digital", "adc"]),
          ("GPIO6", "6", "digital"),
          ("GPIO7", "7", "digital"),
          ("GPIO8", "8", "digital")],
    right=[("GPIO18", "18", "digital"), ("GPIO19", "19", "digital"),
           ("GPIO20", "20", "digital"), ("GPIO21", "21", "digital"),
           ("GPIO0", "0", "digital", ["digital", "adc"]),
           ("GPIO1", "1", "digital", ["digital", "adc"]),
           ("GND2", "G", "gnd", ["gnd"], 0),
           ("GPIO10", "10", "digital"), ("GPIO9", "9", "digital")],
    family="ESP32", logic=3.3, led=(10.5, 20.0),
    note="默认板（NanoCode 同款）：板载 LED 在 GPIO8，反接（LOW 亮）",
    caps={"analog_bits": 12, "builtin_led": "GPIO8"},
))

# ---------------------------------------------------------------- ESP32-S3
add(board(
    "esp32-s3-devkitc-1", "ESP32-S3-DevKitC-1", "ESP32-S3-WROOM-1", 25.5, 63.0,
    left=[("3V3", "3V3", "power", ["power"], 3.3),
          ("3V3B", "3V3", "power", ["power"], 3.3),
          ("RST", "RST", "other"),
          ("GPIO4", "4", "digital", ["digital", "adc"]),
          ("GPIO5", "5", "digital", ["digital", "adc"]),
          ("GPIO6", "6", "digital"),
          ("GPIO7", "7", "digital"),
          ("GPIO15", "15", "digital"),
          ("GPIO16", "16", "digital"),
          ("GPIO17", "17", "digital"),
          ("GPIO18", "18", "digital"),
          ("GPIO8", "8", "digital")],
    right=[("GPIO3", "3", "digital", ["digital", "adc"]),
           ("GPIO46", "46", "digital"),
           ("GPIO9", "9", "digital"),
           ("GPIO10", "10", "digital"),
           ("GPIO11", "11", "digital"),
           ("GPIO12", "12", "digital"),
           ("GPIO13", "13", "digital"),
           ("GPIO14", "14", "digital"),
           ("GPIO21", "21", "digital"),
           ("GPIO47", "47", "digital"),
           ("GPIO48", "48", "digital"),
           ("GND1", "G", "gnd", ["gnd"], 0)],
    family="ESP32", logic=3.3, led=None,
    note="S3 双核 + USB OTG；板载 RGB 灯在 GPIO48（WS2812）",
    caps={"analog_bits": 12, "builtin_led": None},
))

# ---------------------------------------------------------------- ESP32 WROOM
add(board(
    "esp32-wroom-32-devkit-v1", "ESP32-WROOM-32 DevKit V1", "ESP32-WROOM-32", 27.5, 55.0,
    left=[("3V3", "3V3", "power", ["power"], 3.3),
          ("EN", "EN", "other"),
          ("GPIO36", "36", "analog", ["analog"]),
          ("GPIO39", "39", "analog", ["analog"]),
          ("GPIO34", "34", "analog", ["analog"]),
          ("GPIO35", "35", "analog", ["analog"]),
          ("GPIO32", "32", "digital", ["digital", "adc"]),
          ("GPIO33", "33", "digital", ["digital", "adc"]),
          ("GPIO25", "25", "digital"),
          ("GPIO26", "26", "digital"),
          ("GPIO27", "27", "digital"),
          ("GPIO14", "14", "digital"),
          ("GPIO12", "12", "digital"),
          ("GND1", "G", "gnd", ["gnd"], 0),
          ("GPIO13", "13", "digital")],
    right=[("VIN", "VIN", "power", ["power"], 5),
           ("GND2", "G", "gnd", ["gnd"], 0),
           ("GPIO23", "23", "digital"),
           ("GPIO22", "22", "digital"),
           ("GPIO1", "TX", "digital", ["digital", "uart_tx"]),
           ("GPIO3", "RX", "digital", ["digital", "uart_rx"]),
           ("GPIO21", "21", "digital"),
           ("GND3", "G", "gnd", ["gnd"], 0),
           ("GPIO19", "19", "digital"),
           ("GPIO18", "18", "digital"),
           ("GPIO5", "5", "digital"),
           ("GPIO17", "17", "digital"),
           ("GPIO16", "16", "digital"),
           ("GPIO4", "4", "digital"),
           ("GPIO0", "0", "digital")],
    family="ESP32", logic=3.3, led=(4.0, 22.0),
    note="最经典的 ESP32 开发板；板载 LED 在 GPIO2（很多板子是 GPIO2）",
    caps={"analog_bits": 12, "builtin_led": "GPIO2"},
))

# ---------------------------------------------------------------- Arduino Uno
add(board(
    "arduino-uno-r3", "Arduino Uno R3", "ATmega328P", 68.6, 53.4,
    left=[("IOREF", "IOREF", "other"),
          ("RESET", "RESET", "other"),
          ("3V3", "3V3", "power", ["power"], 3.3),
          ("5V", "5V", "power", ["power"], 5),
          ("GND1", "GND", "gnd", ["gnd"], 0),
          ("GND2", "GND", "gnd", ["gnd"], 0),
          ("VIN", "VIN", "power", ["power"], 9),
          ("A0", "A0", "analog", ["analog", "digital"]),
          ("A1", "A1", "analog", ["analog", "digital"]),
          ("A2", "A2", "analog", ["analog", "digital"]),
          ("A3", "A3", "analog", ["analog", "digital"]),
          ("A4", "A4", "analog", ["analog", "digital", "i2c_sda"]),
          ("A5", "A5", "analog", ["analog", "digital", "i2c_scl"])],
    right=[("D13", "13", "digital"),
           ("D12", "12", "digital"),
           ("D11", "11", "pwm", ["digital", "pwm", "spi_mosi"]),
           ("D10", "10", "pwm", ["digital", "pwm", "spi_ss"]),
           ("D9", "9", "pwm", ["digital", "pwm"]),
           ("D8", "8", "digital"),
           ("D7", "7", "digital"),
           ("D6", "6", "pwm", ["digital", "pwm"]),
           ("D5", "5", "pwm", ["digital", "pwm"]),
           ("D4", "4", "digital"),
           ("D3", "3", "pwm", ["digital", "pwm"]),
           ("D2", "2", "digital"),
           ("D1", "1/TX", "digital", ["digital", "uart_tx"]),
           ("D0", "0/RX", "digital", ["digital", "uart_rx"])],
    family="AVR", logic=5, color="#0d6b8f", led=(56.0, 30.0),
    note="经典入门板（ATmega328P，16MHz，5V）；板载 LED 在 D13",
    caps={"analog_bits": 10, "builtin_led": "D13"},
))

# ---------------------------------------------------------------- Arduino Nano
add(board(
    "arduino-nano", "Arduino Nano", "ATmega328P", 18.0, 45.0,
    left=[("D13", "13", "digital"), ("3V3", "3V3", "power", ["power"], 3.3),
          ("AREF", "AREF", "other"), ("A0", "A0", "analog", ["analog"]),
          ("A1", "A1", "analog", ["analog"]), ("A2", "A2", "analog", ["analog"]),
          ("A3", "A3", "analog", ["analog"]), ("A4", "A4", "analog", ["analog", "i2c_sda"]),
          ("A5", "A5", "analog", ["analog", "i2c_scl"]), ("A6", "A6", "analog", ["analog"]),
          ("A7", "A7", "analog", ["analog"]), ("5V", "5V", "power", ["power"], 5),
          ("RST", "RST", "other"), ("GND1", "GND", "gnd", ["gnd"], 0),
          ("VIN", "VIN", "power", ["power"], 9)],
    right=[("D12", "12", "digital"), ("D11", "11", "pwm", ["digital", "pwm"]),
           ("D10", "10", "pwm", ["digital", "pwm"]), ("D9", "9", "pwm", ["digital", "pwm"]),
           ("D8", "8", "digital"), ("D7", "7", "digital"),
           ("D6", "6", "pwm", ["digital", "pwm"]), ("D5", "5", "pwm", ["digital", "pwm"]),
           ("D4", "4", "digital"), ("D3", "3", "pwm", ["digital", "pwm"]),
           ("D2", "2", "digital"), ("GND2", "GND", "gnd", ["gnd"], 0),
           ("RST2", "RST", "other"), ("D0", "0/RX", "digital", ["digital", "uart_rx"]),
           ("D1", "1/TX", "digital", ["digital", "uart_tx"])],
    family="AVR", logic=5, color="#0d6b8f", led=(22.0, 6.0),
    note="面包板友好小板（15×2 排针，2.54mm）",
    caps={"analog_bits": 10, "builtin_led": "D13"},
))

# ---------------------------------------------------------------- STM32 Blue Pill
add(board(
    "stm32-blue-pill", "STM32 Blue Pill", "STM32F103C8T6", 22.5, 53.0,
    left=[("VB", "VB", "power", ["power"], 5),
          ("PC13", "C13", "digital"),
          ("PC14", "C14", "digital"),
          ("PC15", "C15", "digital"),
          ("PA0", "A0", "analog", ["analog", "digital"]),
          ("PA1", "A1", "analog", ["analog", "digital"]),
          ("PA2", "A2", "analog", ["analog", "digital", "uart_tx"]),
          ("PA3", "A3", "analog", ["analog", "digital", "uart_rx"]),
          ("PA4", "A4", "analog", ["analog", "digital"]),
          ("PA5", "A5", "analog", ["analog", "digital"]),
          ("PA6", "A6", "analog", ["analog", "digital"]),
          ("PA7", "A7", "analog", ["analog", "digital"]),
          ("PB0", "B0", "analog", ["analog", "digital"]),
          ("PB1", "B1", "analog", ["analog", "digital"]),
          ("PB10", "B10", "digital"),
          ("PB11", "B11", "digital")],
    right=[("GND1", "G", "gnd", ["gnd"], 0), ("GND2", "G", "gnd", ["gnd"], 0),
           ("3V3", "3V3", "power", ["power"], 3.3),
           ("PB9", "B9", "digital"), ("PB8", "B8", "digital"),
           ("PB7", "B7", "digital"), ("PB6", "B6", "digital"),
           ("PB5", "B5", "digital"), ("PB4", "B4", "digital"),
           ("PB3", "B3", "digital"), ("PA15", "A15", "digital"),
           ("PA12", "A12", "digital", ["digital", "usb_dp"]),
           ("PA11", "A11", "digital", ["digital", "usb_dm"]),
           ("PA10", "A10", "digital", ["digital", "uart_rx"]),
           ("PA9", "A9", "digital", ["digital", "uart_tx"]),
           ("PA8", "A8", "digital")],
    family="STM32", logic=3.3, color="#123a6b", led=(46.0, 4.0),
    note="蓝药丸（F103C8T6，72MHz）；板载 LED 在 PC13（低电平亮）",
    caps={"analog_bits": 12, "builtin_led": "PC13"},
))

# ---------------------------------------------------------------- Raspberry Pi Pico
add(board(
    "raspberry-pi-pico", "Raspberry Pi Pico", "RP2040", 21.0, 51.0,
    left=[("GP0", "0", "digital", ["digital", "uart_tx"]),
          ("GP1", "1", "digital", ["digital", "uart_rx"]),
          ("GND1", "G", "gnd", ["gnd"], 0),
          ("GP2", "2", "digital"), ("GP3", "3", "digital"),
          ("GP4", "4", "digital"), ("GP5", "5", "digital"),
          ("GND2", "G", "gnd", ["gnd"], 0),
          ("GP6", "6", "digital"), ("GP7", "7", "digital"),
          ("GP8", "8", "digital"), ("GP9", "9", "digital"),
          ("GND3", "G", "gnd", ["gnd"], 0),
          ("GP10", "10", "digital"), ("GP11", "11", "digital"),
          ("GP12", "12", "digital"), ("GP13", "13", "digital"),
          ("GND4", "G", "gnd", ["gnd"], 0),
          ("GP14", "14", "digital"), ("GP15", "15", "digital")],
    right=[("VBUS", "VBUS", "power", ["power"], 5),
           ("GP16", "16", "digital"), ("GP17", "17", "digital"),
           ("GND5", "G", "gnd", ["gnd"], 0),
           ("GP18", "18", "digital"), ("GP19", "19", "digital"),
           ("GP20", "20", "digital"), ("GP21", "21", "digital"),
           ("GND6", "G", "gnd", ["gnd"], 0),
           ("GP22", "22", "digital"), ("RUN", "RUN", "other"),
           ("GP26", "26", "analog", ["analog"]), ("GP27", "27", "analog", ["analog"]),
           ("GND7", "G", "gnd", ["gnd"], 0),
           ("GP28", "28", "analog", ["analog"]), ("ADC_VREF", "VREF", "other"),
           ("3V3", "3V3", "power", ["power"], 3.3), ("3V3_EN", "3V3_EN", "other"),
           ("GND8", "G", "gnd", ["gnd"], 0),
           ("GP25", "25", "digital")],
    family="RP2040", logic=3.3, color="#0f3d2e", led=(25.0, 15.5),
    note="双核 133MHz；板载 LED 在 GP25",
    caps={"analog_bits": 12, "builtin_led": "GP25"},
))

# ---------------------------------------------------------------- NodeMCU
add(board(
    "nodemcu-v3", "NodeMCU V3 (ESP8266)", "ESP8266-12F", 25.5, 49.0,
    left=[("A0", "A0", "analog", ["analog"]),
          ("RSV", "RSV", "other"),
          ("RSV2", "RSV", "other"),
          ("SD3", "SD3", "digital"), ("SD2", "SD2", "digital"),
          ("SD1", "SD1", "digital"), ("CMD", "CMD", "digital"),
          ("SD0", "SD0", "digital"), ("CLK", "CLK", "digital"),
          ("GND1", "G", "gnd", ["gnd"], 0),
          ("3V3", "3V3", "power", ["power"], 3.3),
          ("EN", "EN", "other"), ("RST", "RST", "other"),
          ("GND2", "G", "gnd", ["gnd"], 0), ("VIN", "VIN", "power", ["power"], 5)],
    right=[("D0", "D0", "digital", ["digital"]),
           ("D1", "D1", "digital", ["digital", "i2c_scl"]),
           ("D2", "D2", "digital", ["digital", "i2c_sda"]),
           ("D3", "D3", "digital"), ("D4", "D4", "digital"),
           ("D5", "D5", "digital"), ("D6", "D6", "digital"),
           ("D7", "D7", "digital"), ("D8", "D8", "digital"),
           ("RX", "RX", "digital", ["digital", "uart_rx"]),
           ("TX", "TX", "digital", ["digital", "uart_tx"]),
           ("GND3", "G", "gnd", ["gnd"], 0),
           ("GND4", "G", "gnd", ["gnd"], 0),
           ("3V3B", "3V3", "power", ["power"], 3.3),
           ("VIN2", "VIN", "power", ["power"], 5)],
    family="ESP8266", logic=3.3, led=(4.0, 12.0),
    note="ESP8266 NodeMCU；板载 LED 在 D2（GPIO2，低电平亮）",
    caps={"analog_bits": 10, "builtin_led": "D2"},
))


# ---------------------------------------------------------------- 第 11 轮补充板
add(board(
    "arduino-uno-r4-wifi", "Arduino Uno R4 WiFi", "RA4M1", 68.6, 53.4,
    left=[("RESET", "RESET", "other"), ("3V3", "3V3", "power", ["power"], 3.3),
          ("5V", "5V", "power", ["power"], 5), ("GND1", "GND", "gnd", ["gnd"], 0),
          ("GND2", "GND", "gnd", ["gnd"], 0), ("VIN", "VIN", "power", ["power"], 9),
          ("A0", "A0", "analog", ["analog"]), ("A1", "A1", "analog", ["analog"]),
          ("A2", "A2", "analog", ["analog"]), ("A3", "A3", "analog", ["analog"]),
          ("A4", "A4", "analog", ["analog", "i2c_sda"]), ("A5", "A5", "analog", ["analog", "i2c_scl"]),
          ("D13", "13", "digital")],
    right=[("D12", "12", "digital"), ("D11", "11", "pwm", ["digital", "pwm"]),
           ("D10", "10", "pwm", ["digital", "pwm"]), ("D9", "9", "pwm", ["digital", "pwm"]),
           ("D8", "8", "digital"), ("D7", "7", "digital"),
           ("D6", "6", "pwm", ["digital", "pwm"]), ("D5", "5", "pwm", ["digital", "pwm"]),
           ("D4", "4", "digital"), ("D3", "3", "pwm", ["digital", "pwm"]),
           ("D2", "2", "digital"), ("D1", "1/TX", "digital", ["digital", "uart_tx"]),
           ("D0", "0/RX", "digital", ["digital", "uart_rx"])],
    family="Renesas", logic=5, color="#0d6b8f", led=(56.0, 30.0),
    note="R4 WiFi（RA4M1 + ESP32-S3 无线）；板载 LED 在 D13",
    caps={"analog_bits": 14, "builtin_led": "D13"},
))

add(board(
    "raspberry-pi-pico-w", "Raspberry Pi Pico W", "RP2040 + CYW43439", 21.0, 51.0,
    left=[("GP0", "0", "digital", ["digital", "uart_tx"]),
          ("GP1", "1", "digital", ["digital", "uart_rx"]),
          ("GND1", "G", "gnd", ["gnd"], 0), ("GP2", "2", "digital"), ("GP3", "3", "digital"),
          ("GP4", "4", "digital"), ("GP5", "5", "digital"), ("GND2", "G", "gnd", ["gnd"], 0),
          ("GP6", "6", "digital"), ("GP7", "7", "digital"), ("GP8", "8", "digital"),
          ("GP9", "9", "digital"), ("GND3", "G", "gnd", ["gnd"], 0),
          ("GP10", "10", "digital"), ("GP11", "11", "digital")],
    right=[("VBUS", "VBUS", "power", ["power"], 5), ("GP16", "16", "digital"),
           ("GP17", "17", "digital"), ("GND4", "G", "gnd", ["gnd"], 0),
           ("GP18", "18", "digital"), ("GP19", "19", "digital"), ("GP20", "20", "digital"),
           ("GP21", "21", "digital"), ("GND5", "G", "gnd", ["gnd"], 0),
           ("GP22", "22", "digital"), ("RUN", "RUN", "other"),
           ("GP26", "26", "analog", ["analog"]), ("GP27", "27", "analog", ["analog"]),
           ("GND6", "G", "gnd", ["gnd"], 0), ("GP28", "28", "analog", ["analog"])],
    family="RP2040", logic=3.3, color="#0f3d2e", led=(10.5, 38.0),
    note="带 WiFi 的 Pico；板载 LED 在 GP25（模块内部）",
    caps={"analog_bits": 12, "builtin_led": "GP25"},
))

add(board(
    "esp32-cam", "ESP32-CAM", "ESP32-S", 27.0, 40.5,
    left=[("5V", "5V", "power", ["power"], 5), ("GND1", "G", "gnd", ["gnd"], 0),
          ("GPIO12", "12", "digital"), ("GPIO13", "13", "digital"),
          ("GPIO15", "15", "digital"), ("GPIO14", "14", "digital"),
          ("GPIO2", "2", "digital"), ("GPIO4", "4", "digital")],
    right=[("GPIO16", "16", "digital"), ("GPIO0", "0", "digital"),
           ("GND2", "G", "gnd", ["gnd"], 0), ("3V3", "3V3", "power", ["power"], 3.3),
           ("GPIO1", "1/TX", "digital", ["digital", "uart_tx"]),
           ("GPIO3", "3/RX", "digital", ["digital", "uart_rx"]),
           ("GPIO33", "33", "digital"), ("GND3", "G", "gnd", ["gnd"], 0)],
    family="ESP32", logic=3.3, led=(4.0, 20.0),
    note="带摄像头的小板；烧录要接 USB-TTL，GPIO0 拉低进下载模式",
    caps={"analog_bits": 12, "builtin_led": "GPIO33"},
))

add(board(
    "teensy-4-0", "Teensy 4.0", "i.MXRT1062", 17.8, 35.6,
    left=[("GND1", "G", "gnd", ["gnd"], 0), ("0", "0", "digital", ["digital", "uart_rx"]),
          ("1", "1", "digital", ["digital", "uart_tx"]), ("2", "2", "digital"),
          ("3", "3", "digital"), ("4", "4", "digital"), ("5", "5", "digital"),
          ("6", "6", "digital"), ("7", "7", "digital"), ("8", "8", "digital"),
          ("9", "9", "digital"), ("10", "10", "digital")],
    right=[("VIN", "VIN", "power", ["power"], 5), ("GND2", "G", "gnd", ["gnd"], 0),
           ("3V3", "3V3", "power", ["power"], 3.3), ("23", "23", "digital"),
           ("22", "22", "digital"), ("21", "21", "digital"), ("20", "20", "digital"),
           ("19", "19", "digital"), ("18", "18", "digital"), ("17", "17", "digital"),
           ("16", "16", "digital"), ("15", "15", "digital"), ("14", "14", "analog", ["analog"])],
    family="Other", logic=3.3, color="#243b2a", led=(8.0, 6.0),
    note="600MHz Cortex-M7；板载 LED 在 13",
    caps={"analog_bits": 12, "builtin_led": "13"},
))


# ------------------------------------------------------- 可调电源（教学/烧毁实验用）
add(board(
    "bench-supply", "可调直流电源（3–12V）", "Bench PSU", 60.0, 40.0,
    left=[("V3_3", "3.3V", "power", ["power"], 3.3),
          ("V5", "5V", "power", ["power"], 5),
          ("V6", "6V", "power", ["power"], 6),
          ("V7", "7.5V", "power", ["power"], 7.5),
          ("V9", "9V", "power", ["power"], 9),
          ("V12", "12V", "power", ["power"], 12),
          ("GND1", "GND", "gnd", ["gnd"], 0)],
    right=[("GND2", "GND", "gnd", ["gnd"], 0),
           ("OUT_A", "OUT+", "power", ["power"], 5),
           ("OUT_B", "OUT−", "gnd", ["gnd"], 0)],
    family="Other", logic=5, color="#2b2f36", led=(54.0, 6.0),
    note="教学用的可调电源：不同电压档位就是不同供电，用来验证过压烧毁（5V 灯接 6V 有概率烧、接 10V 必烧）",
    caps={"analog_bits": 10, "builtin_led": None},
))

BOARD_LIST = list(BOARDS.values())


def get_board(bid):
    return BOARDS.get(bid) or BOARD_LIST[0]

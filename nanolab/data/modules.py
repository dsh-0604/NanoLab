# -*- coding: utf-8 -*-
"""配件几何数据（单位毫米，按真实模块尺寸；排针按 2.54mm）"""

from __future__ import annotations

PITCH = 2.54


def _pins(items, edge, start=None, cross=None):
    """items: [(id, label, role)] ；edge: bottom/top/left/right
    返回带 mm 坐标的引脚列表（沿边等距 2.54）"""
    out = []
    n = len(items)
    for i, it in enumerate(items):
        pid, label, role = it[0], it[1], it[2]
        out.append({"id": pid, "label": label, "role": role, "edge": edge,
                    "slot": i, "_n": n})
    return out


def module(mid, name, w, h, pins, *, category="module", color="#1f6f4a",
           features=None, behavior=None, controls=None, doc="", keywords=(), props=None,
           pin_edge="bottom", pin_margin=3.0, pin_cross=2.2):
    """pins 用 (id, label, role) 序列；坐标在构建时算好"""
    out_pins = []
    n = len(pins)
    for i, it in enumerate(pins):
        pid, label, role = it[0], it[1], it[2]
        if pin_edge in ("bottom", "top"):
            span = (n - 1) * PITCH
            x = (w - span) / 2 + i * PITCH
            y = h - pin_cross if pin_edge == "bottom" else pin_cross
        else:
            span = (n - 1) * PITCH
            y = (h - span) / 2 + i * PITCH
            x = w - pin_cross if pin_edge == "right" else pin_cross
        out_pins.append({"id": pid, "label": label, "role": role,
                         "edge": pin_edge, "x": round(x, 2), "y": round(y, 2)})
    return {
        "id": mid, "name": name, "w": float(w), "h": float(h),
        "category": category, "color": color, "pins": out_pins,
        "features": features or [], "behavior": behavior or mid,
        "controls": controls or [], "doc": doc, "keywords": list(keywords),
        "props": props or {},
    }


MODULES = {}


def add(m):
    MODULES[m["id"]] = m


def slider(key, label, lo, hi, val, step=1, unit=""):
    return {"key": key, "label": label, "type": "slider", "min": lo, "max": hi,
            "value": val, "step": step, "unit": unit}


def toggle(key, label, value=False):
    return {"key": key, "label": label, "type": "toggle", "value": value}


def button(key, label):
    return {"key": key, "label": label, "type": "button", "value": False}


# ------------------------------------------------------------------ 输入类
add(module("button-module", "按键模块", 24.0, 16.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "button", "x": 12.0, "y": 7.0, "r": 3.6}],
           controls=[{"key": "pressed", "label": "按住按键", "type": "hold", "value": False}],
           doc="VCC→3V3/5V，GND→GND，OUT→任意数字口；按下时 OUT 输出高电平（模块自带上拉）",
           keywords=["按键", "button", "开关", "输入"]))

add(module("potentiometer", "10k 电位器（旋钮）", 32.0, 14.0,
           [("VCC", "VCC", "power"), ("WIPER", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "knob", "x": 24.0, "y": 7.0, "r": 4.6}],
           controls=[slider("value", "旋钮位置", 0, 100, 50, 1, "%")],
           doc="两端接 3V3/GND，中间脚接模拟口；旋钮位置 → 0~1023",
           keywords=["电位器", "旋钮", "pot", "可调电阻"]))

add(module("ldr", "光敏电阻模块", 32.0, 14.0,
           [("VCC", "VCC", "power"), ("AO", "AO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "grid", "x": 7.0, "y": 7.0, "r": 3.2, "rows": 3, "cols": 2}],
           controls=[slider("lux", "光照强度", 0, 1000, 300, 1, "lx")],
           doc="AO 输出随光照变化：亮 → 电压高（仿真里 lux 越大读数越大）",
           keywords=["光敏", "光照", "ldr", "亮度"]))

add(module("flame-sensor", "火焰传感器", 30.0, 16.0,
           [("VCC", "VCC", "power"), ("AO", "AO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "grid", "x": 7.0, "y": 8.0, "r": 2.6, "rows": 2, "cols": 2}],
           controls=[slider("level", "火焰强度", 0, 100, 10, 1, "%")],
           doc="靠近火源时 AO 电压升高（仿真：level 越大读数越大）",
           keywords=["火焰", "火", "flame"]))

add(module("soil-moisture", "土壤湿度传感器", 60.0, 20.0,
           [("VCC", "VCC", "power"), ("AO", "AO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "probe", "x": 40.0, "y": 10.0}],
           controls=[slider("moisture", "土壤湿度", 0, 100, 45, 1, "%")],
           doc="插进土里；湿度越高读数越大",
           keywords=["土壤", "湿度", "soil", "浇花"]))

add(module("rain-sensor", "雨滴传感器", 32.0, 16.0,
           [("VCC", "VCC", "power"), ("AO", "AO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "grid", "x": 8.0, "y": 8.0, "r": 2.2, "rows": 3, "cols": 3}],
           controls=[slider("rain", "雨量", 0, 100, 0, 1, "%")],
           doc="雨水越多 AO 读数越大（雨滴板）",
           keywords=["雨水", "雨滴", "rain"]))

add(module("mq2", "MQ-2 烟雾/燃气传感器", 32.0, 22.0,
           [("VCC", "VCC", "power"), ("AO", "AO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "grid", "x": 8.0, "y": 11.0, "r": 5.0, "rows": 2, "cols": 2}],
           controls=[slider("smoke", "烟雾浓度", 0, 1000, 120, 1, "ppm")],
           doc="烟雾/可燃气体浓度越高，AO 读数越大",
           keywords=["烟雾", "燃气", "mq2", "气体"]))

add(module("sound-sensor", "声音传感器", 32.0, 14.0,
           [("VCC", "VCC", "power"), ("AO", "AO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "mic", "x": 24.0, "y": 7.0}],
           controls=[slider("level", "环境音量", 0, 100, 30, 1, "%")],
           doc="麦克风模块：声音越大 AO 读数越大",
           keywords=["声音", "麦克风", "sound", "噪音"]))

add(module("joystick", "双轴摇杆模块", 34.0, 34.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"), ("X", "X", "signal"),
            ("Y", "Y", "signal"), ("SW", "SW", "signal")],
           category="input", color="#1e5f4a",
           features=[{"type": "stick", "x": 15.0, "y": 14.0}],
           controls=[slider("x", "X 轴", 0, 100, 50, 1, "%"),
                     slider("y", "Y 轴", 0, 100, 50, 1, "%"),
                     toggle("sw", "按下（SW）")],
           doc="X/Y 接模拟口，SW 接数字口（按下为低）",
           keywords=["摇杆", "joystick", "游戏杆"]))

add(module("pir", "HC-SR501 人体红外", 32.0, 24.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "dome", "x": 16.0, "y": 9.0, "r": 8.0}],
           controls=[toggle("motion", "有人经过")],
           doc="检测到人体移动后 OUT 输出高电平并保持约 2 秒",
           keywords=["人体", "红外", "pir", "感应"]))

add(module("hc-sr04", "HC-SR04 超声波测距", 45.0, 20.0,
           [("VCC", "VCC", "power"), ("TRIG", "TRIG", "signal"),
            ("ECHO", "ECHO", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1a4f6e",
           features=[{"type": "ultrasonic", "x": 24.0, "y": 10.0}],
           controls=[slider("dist", "障碍物距离", 2, 400, 100, 1, "cm")],
           doc="TRIG 发 10µs 脉冲，ECHO 回波宽度 = 距离×58µs；pulseIn 直接读",
           keywords=["超声波", "测距", "sr04", "距离"]))

add(module("ir-receiver", "VS1838B 红外接收", 20.0, 12.0,
           [("OUT", "OUT", "signal"), ("GND", "GND", "gnd"), ("VCC", "VCC", "power")],
           category="input", color="#2a2f36",
           features=[{"type": "ir", "x": 10.0, "y": 5.5}],
           controls=[button("send", "遥控器按一下")],
           doc="OUT 接数字口；配 IRremote 库读取 NEC 码",
           keywords=["红外", "接收", "vs1838", "ir", "遥控"]))

add(module("dht11", "DHT11 温湿度传感器", 12.0, 15.5,
           [("VCC", "VCC", "power"), ("DATA", "DATA", "signal"), ("GND", "GND", "gnd")],
           category="sensor", color="#d8dee6", pin_cross=1.6,
           features=[{"type": "dht", "x": 6.0, "y": 6.0}],
           controls=[slider("temp", "温度", -10, 60, 25, 0.5, "°C"),
                     slider("humi", "湿度", 0, 100, 55, 1, "%")],
           doc="VCC→3V3/5V，DATA→数字口（4.7k 上拉已内置），GND→GND",
           keywords=["dht11", "温湿度", "温度", "湿度"]))

add(module("dht22", "DHT22 温湿度传感器", 15.1, 25.1,
           [("VCC", "VCC", "power"), ("DATA", "DATA", "signal"), ("GND", "GND", "gnd")],
           category="sensor", color="#eef1f5", pin_cross=1.8,
           features=[{"type": "dht", "x": 7.5, "y": 9.0}],
           controls=[slider("temp", "温度", -40, 80, 25, 0.5, "°C"),
                     slider("humi", "湿度", 0, 100, 60, 1, "%")],
           doc="VCC→3V3/5V，DATA→数字口，GND→GND（精度比 DHT11 高）",
           keywords=["dht22", "am2302", "温湿度", "温度", "湿度"]))

add(module("ds18b20", "DS18B20 防水温度探头", 22.0, 12.0,
           [("VCC", "VCC", "power"), ("DATA", "DATA", "signal"), ("GND", "GND", "gnd")],
           category="sensor", color="#2a2f36",
           features=[{"type": "probe", "x": 12.0, "y": 6.0}],
           controls=[slider("temp", "水温", -55, 125, 26, 0.5, "°C")],
           doc="VCC→3V3/5V，DATA→数字口（4.7k 上拉），GND→GND；常用来测水温",
           keywords=["ds18b20", "18b20", "水温", "温度", "探头"]))

add(module("encoder", "旋转编码器 EC11", 32.0, 18.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"), ("A", "A", "signal"),
            ("B", "B", "signal"), ("SW", "SW", "signal")],
           category="input", color="#1e5f4a",
           features=[{"type": "knob", "x": 22.0, "y": 9.0, "r": 5.0}],
           controls=[slider("ticks", "转一格", -20, 20, 0, 1, "")],
           doc="A/B 接数字口，转动时输出相位差；SW 是按下键",
           keywords=["编码器", "ec11", "旋钮", "encoder"]))

# ------------------------------------------------------------------ 显示类
add(module("ssd1306-oled", "0.96\" OLED SSD1306 (I2C)", 27.3, 27.3,
           [("GND", "GND", "gnd"), ("VCC", "VCC", "power"),
            ("SCL", "SCL", "signal"), ("SDA", "SDA", "signal")],
           category="display", color="#14181d", pin_edge="bottom", pin_cross=2.0,
           features=[{"type": "screen", "x": 1.8, "y": 1.8, "w": 23.7, "h": 14.0,
                      "res": (128, 64)}],
           controls=[toggle("invert", "反白显示")],
           doc="I2C：SDA/SCL 接对应口，地址 0x3C；128×64 单色",
           keywords=["oled", "ssd1306", "屏幕", "显示", "i2c"]))

add(module("lcd1602-i2c", "LCD1602 + I2C 转接板", 80.0, 36.0,
           [("GND", "GND", "gnd"), ("VCC", "VCC", "power"),
            ("SDA", "SDA", "signal"), ("SCL", "SCL", "signal")],
           category="display", color="#1b6b3a", pin_edge="top", pin_cross=2.0,
           features=[{"type": "lcd", "x": 2.0, "y": 12.0, "w": 70.0, "h": 22.0,
                      "cols": 16, "rows": 2}],
           controls=[toggle("backlight", "背光", True)],
           doc="I2C 转接板：GND/VCC/SDA/SCL；地址常见 0x27 或 0x3F",
           keywords=["lcd", "1602", "液晶", "显示", "i2c"]))

add(module("tm1637", "TM1637 四位数码管", 42.0, 24.0,
           [("GND", "GND", "gnd"), ("VCC", "VCC", "power"),
            ("DIO", "DIO", "signal"), ("CLK", "CLK", "signal")],
           category="display", color="#161a20", pin_edge="top", pin_cross=2.0,
           features=[{"type": "digits", "x": 3.0, "y": 8.0, "w": 36.0, "h": 14.0}],
           controls=[slider("brightness", "亮度", 0, 7, 5, 1, "")],
           doc="CLK/DIO 接任意两个数字口；4 位 7 段数码管",
           keywords=["数码管", "tm1637", "四位", "显示"]))

add(module("max7219", "8×8 LED 点阵 MAX7219", 32.0, 32.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"),
            ("DIN", "DIN", "signal"), ("CS", "CS", "signal"), ("CLK", "CLK", "signal")],
           category="display", color="#161a20", pin_edge="left", pin_cross=2.0,
           features=[{"type": "matrix", "x": 6.0, "y": 6.0, "w": 22.0, "h": 22.0}],
           doc="SPI 接法：DIN/CS/CLK；8×8 红色点阵",
           keywords=["点阵", "max7219", "8x8", "显示"]))

# ------------------------------------------------------------------ 输出类
add(module("led", "LED 发光二极管", 5.9, 5.9,
           [("A", "A", "signal"), ("K", "K", "gnd")],
           category="actuator", color="#7a1620", pin_cross=1.2,
           features=[{"type": "led", "x": 2.95, "y": 2.4, "r": 2.4}],
           controls=[{"key": "color", "label": "颜色", "type": "select", "value": "red",
                      "options": ["red", "green", "blue", "yellow", "white"]}],
           doc="长脚 A 接数字口，短脚 K 接 GND（串 220Ω，仿真已内置）",
           keywords=["led", "灯", "发光二极管"]))


add(module("resistor", "电阻（可调阻值）", 22.0, 10.0,
           [("1", "1", "signal"), ("2", "2", "signal")],
           category="actuator", color="#c8b48a", pin_edge="left", pin_cross=2.0,
           features=[{"type": "resistor", "x": 7.0, "y": 5.0, "w": 9.0}],
           controls=[slider("ohms", "阻值", 10, 5000, 220, 10, "Ω")],
           doc="串在 LED 和引脚之间限流：5V 时 220Ω≈14mA、1kΩ≈3mA；阻值太小会烧电阻/LED（右下有烧毁概率）",
           keywords=["电阻", "resistor", "限流", "欧姆"]))

add(module("rgb-led", "RGB 共阴 LED", 5.9, 5.9,
           [("R", "R", "signal"), ("G", "G", "signal"),
            ("B", "B", "signal"), ("K", "K", "gnd")],
           category="actuator", color="#3a3f4a", pin_cross=1.2,
           features=[{"type": "rgbled", "x": 2.95, "y": 2.4, "r": 2.6}],
           doc="R/G/B 分别接三个支持 PWM 的脚，K 接 GND；analogWrite 混色",
           keywords=["rgb", "全彩", "三色"]))

add(module("ws2812-ring", "WS2812B 灯环 8 灯", 24.0, 24.0,
           [("5V", "5V", "power"), ("DIN", "DIN", "signal"), ("GND", "GND", "gnd")],
           category="actuator", color="#14181d", pin_cross=1.4,
           features=[{"type": "ring", "x": 12.0, "y": 12.0, "r": 10.0, "n": 8}],
           doc="DIN 接数字口；5V 单独供电更稳（仿真无所谓）",
           keywords=["ws2812", "灯环", "rgb灯", "neopixel"]))

add(module("buzzer-active", "有源蜂鸣器", 12.0, 9.5,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#1c1f24", pin_cross=1.2,
           features=[{"type": "buzzer", "x": 6.0, "y": 3.6, "r": 3.4}],
           doc="有源：给高电平就响（不用 tone()）",
           keywords=["蜂鸣器", "有源", "buzzer"]))

add(module("buzzer-passive", "无源蜂鸣器", 12.0, 9.5,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#1c1f24", pin_cross=1.2,
           features=[{"type": "buzzer", "x": 6.0, "y": 3.6, "r": 3.4}],
           doc="无源：必须用 tone(引脚, 频率) 才会响",
           keywords=["蜂鸣器", "无源", "tone"]))

add(module("relay-1ch", "单路 5V 继电器模块", 42.0, 25.5,
           [("VCC", "VCC", "power"), ("IN", "IN", "signal"), ("GND", "GND", "gnd")],
           category="actuator", color="#1b3a63",
           features=[{"type": "relay", "x": 14.0, "y": 12.0}],
           controls=[toggle("active_high", "高电平触发", True)],
           doc="IN 高电平吸合（可切成低电平触发）；可控制灯、水泵、电磁锁",
           keywords=["继电器", "relay", "开关"]))

add(module("servo-sg90", "SG90 微型舵机", 22.8, 22.5,
           [("VCC", "VCC", "power"), ("SIG", "SIG", "signal"), ("GND", "GND", "gnd")],
           category="actuator", color="#2a63a8", pin_cross=1.6, pin_edge="bottom",
           features=[{"type": "servo", "x": 11.4, "y": 11.0}],
           doc="信号线接数字口；Servo 库 write(0~180) 控制角度",
           keywords=["舵机", "servo", "sg90", "角度"]))

add(module("stepper-28byj", "28BYJ-48 步进电机 + ULN2003", 35.0, 35.0,
           [("IN1", "IN1", "signal"), ("IN2", "IN2", "signal"),
            ("IN3", "IN3", "signal"), ("IN4", "IN4", "signal"),
            ("VCC", "VCC", "power"), ("GND", "GND", "gnd")],
           category="actuator", color="#1e5f4a", pin_edge="left", pin_cross=2.0,
           features=[{"type": "stepper", "x": 20.0, "y": 17.0}],
           doc="四相线接 4 个数字口；用 Stepper 库一步步转",
           keywords=["步进", "28byj", "电机", "stepper"]))

add(module("motor-l298n", "L298N 电机驱动 + 直流电机", 43.0, 43.0,
           [("IN1", "IN1", "signal"), ("IN2", "IN2", "signal"),
            ("ENA", "ENA", "signal"), ("GND", "GND", "gnd")],
           category="actuator", color="#1b3a63", pin_edge="left", pin_cross=2.0,
           features=[{"type": "motor", "x": 28.0, "y": 12.0}],
           controls=[toggle("reverse", "反转", False)],
           doc="IN1/IN2 控方向，ENA 用 PWM 调速",
           keywords=["电机", "l298n", "马达", "直流"]))

add(module("traffic-light", "交通灯模块", 24.0, 60.0,
           [("R", "R", "signal"), ("Y", "Y", "signal"), ("G", "G", "signal"), ("GND", "GND", "gnd")],
           category="actuator", color="#161a20", pin_edge="bottom", pin_cross=2.0,
           features=[{"type": "traffic", "x": 12.0, "y": 10.0}],
           doc="三个灯分别接三个数字口（高电平点亮）",
           keywords=["交通灯", "红绿灯"]))

add(module("fan", "5V 小风扇", 30.0, 30.0,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#242a33",
           features=[{"type": "fan", "x": 15.0, "y": 15.0}],
           doc="接数字口或 PWM（大功率请加三极管/继电器）",
           keywords=["风扇", "fan"]))

add(module("vibration-motor", "振动马达", 16.0, 10.0,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#242a33", pin_cross=1.4,
           features=[{"type": "vibrate", "x": 8.0, "y": 5.0}],
           doc="接数字口；高电平振动",
           keywords=["振动", "马达", "振动马达"]))

add(module("laser", "激光发射模块", 18.0, 10.0,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#4a3a12", pin_cross=1.4,
           features=[{"type": "laser", "x": 9.0, "y": 5.0}],
           doc="高电平点亮（注意别照眼睛）",
           keywords=["激光", "laser"]))

# ------------------------------------------------------------------ 其它
add(module("breadboard-400", "面包板 400 孔", 84.0, 55.0,
           [], category="module", color="#e8eaf0", pin_cross=1.0,
           features=[{"type": "breadboard", "x": 3.0, "y": 4.0, "w": 78.0, "h": 47.0}],
           doc="只用于摆放，接线还是按引脚连（仿真不需要真的插孔）",
           keywords=["面包板", "breadboard"]))

add(module("power-module", "电源模块 3.3V/5V", 30.0, 20.0,
           [("5V", "5V", "power"), ("GND", "GND", "gnd"), ("3V3", "3V3", "power")],
           category="module", color="#1b3a63",
           features=[{"type": "power", "x": 15.0, "y": 9.0}],
           doc="给面包板供电用（仿真里主要作装饰）",
           keywords=["电源", "供电", "3.3v", "5v"]))

add(module("hc05", "HC-05 蓝牙串口", 27.0, 13.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"),
            ("TXD", "TXD", "signal"), ("RXD", "RXD", "signal")],
           category="module", color="#123a6b",
           features=[{"type": "bt", "x": 13.0, "y": 6.0}],
           controls=[button("send", "手机发来一条消息")],
           doc="TXD/RXD 接板子串口（交叉接线）；仿真里可模拟手机发数据",
           keywords=["蓝牙", "hc05", "串口", "无线"]))

add(module("rtc", "DS3231 时钟模块", 38.0, 22.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"),
            ("SDA", "SDA", "signal"), ("SCL", "SCL", "signal")],
           category="module", color="#1b3a63", pin_edge="left", pin_cross=2.0,
           features=[{"type": "rtc", "x": 22.0, "y": 11.0}],
           doc="I2C 时钟：SDA/SCL 接 I2C 口",
           keywords=["时钟", "rtc", "ds3231", "时间"]))


# ---------------------------- 第 11 轮补充：常见小件 ----------------------------
add(module("hall-switch", "霍尔开关 A3144", 12.0, 8.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "grid", "x": 6.0, "y": 4.0, "r": 2.0, "rows": 1, "cols": 2}],
           controls=[toggle("state", "磁铁靠近")],
           doc="检测磁场：有磁铁 → OUT 输出低电平（模块内部上拉），常用来做门磁/转速",
           keywords=["霍尔", "a3144", "磁", "门磁"]))

add(module("tilt-switch", "倾斜开关 SW-520D", 12.0, 8.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "grid", "x": 6.0, "y": 4.0, "r": 2.0, "rows": 1, "cols": 2}],
           controls=[toggle("state", "倾斜")],
           doc="倾斜到一定角度导通，可做倾倒报警",
           keywords=["倾斜", "sw520d", "角度"]))

add(module("reed-switch", "干簧管", 20.0, 8.0,
           [("1", "1", "signal"), ("2", "2", "signal")],
           category="input", color="#1e5f4a", pin_edge="left",
           features=[{"type": "grid", "x": 10.0, "y": 4.0, "r": 2.2, "rows": 1, "cols": 2}],
           controls=[toggle("state", "磁铁靠近")],
           doc="磁铁靠近时两脚导通（做门窗磁）",
           keywords=["干簧管", "reed", "门窗"]))

add(module("limit-switch", "限位开关", 20.0, 10.0,
           [("COM", "COM", "signal"), ("NO", "NO", "signal"), ("NC", "NC", "signal")],
           category="input", color="#1e5f4a",
           features=[{"type": "button", "x": 15.0, "y": 5.0, "r": 2.2}],
           controls=[{"key": "state", "label": "按住（压下）", "type": "hold", "value": False}],
           doc="机械限位：压下去 NO 导通（3D 打印机常用）",
           keywords=["限位", "微动", "开关"]))

add(module("ttp223", "TTP223 触摸按键", 24.0, 16.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1e5f4a",
           features=[{"type": "button", "x": 12.0, "y": 8.0, "r": 3.2}],
           controls=[{"key": "state", "label": "手指按住", "type": "hold", "value": False}],
           doc="摸一下就输出高电平（电容触摸，不用机械按键）",
           keywords=["触摸", "ttp223", "电容"]))

add(module("button-bare", "轻触按键（裸件 4 脚）", 6.5, 6.5,
           [("1", "1", "signal"), ("2", "2", "signal")],
           category="input", color="#2a2f36",
           features=[{"type": "button", "x": 3.2, "y": 3.2, "r": 2.2}],
           controls=[{"key": "state", "label": "按住", "type": "hold", "value": False}],
           doc="两脚接引脚，按下导通（另一侧两脚内部相连）",
           keywords=["按键", "轻触", "按钮"]))

add(module("ir-pair", "红外对射/避障", 30.0, 10.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="input", color="#1a4f6e",
           features=[{"type": "ir", "x": 22.0, "y": 5.0}],
           controls=[toggle("state", "有障碍物")],
           doc="前方有障碍 → OUT 变低电平（避障小车常用）",
           keywords=["红外", "避障", "对射"]))

add(module("lm35", "LM35 温度传感器", 12.0, 10.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="sensor", color="#2a2f36",
           features=[{"type": "grid", "x": 6.0, "y": 5.0, "r": 2.4, "rows": 2, "cols": 1}],
           controls=[slider("temp", "温度", -10, 100, 25, 0.5, "°C")],
           doc="模拟输出 10mV/°C，analogRead 后换算：V×100",
           keywords=["lm35", "温度", "模拟"]))

add(module("acs712", "ACS712 电流传感器", 30.0, 12.0,
           [("VCC", "VCC", "power"), ("OUT", "OUT", "signal"), ("GND", "GND", "gnd")],
           category="sensor", color="#1e5f4a",
           features=[{"type": "grid", "x": 8.0, "y": 6.0, "r": 2.4, "rows": 2, "cols": 2}],
           controls=[slider("amps", "电流", -30, 30, 1, 0.1, "A")],
           doc="测电流：静止时约 2.5V，每安培变化 66mV（20A 版）",
           keywords=["电流", "acs712", "功率"]))

add(module("water-pump", "5V 小水泵", 40.0, 30.0,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#1b3a63",
           features=[{"type": "motor", "x": 20.0, "y": 15.0}],
           doc="接数字口/继电器控制；高电平抽水（仿真里会转）",
           keywords=["水泵", "pump", "浇水"]))

add(module("solenoid", "电磁锁", 30.0, 20.0,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#3a2a12",
           features=[{"type": "relay", "x": 15.0, "y": 10.0}],
           doc="通电吸合（开门），断电弹簧复位",
           keywords=["电磁锁", "solenoid", "门锁"]))

add(module("ir-led", "红外发射 LED", 12.0, 8.0,
           [("+", "+", "signal"), ("-", "-", "gnd")],
           category="actuator", color="#2a1f2f",
           features=[{"type": "laser", "x": 6.0, "y": 4.0}],
           doc="红外发射管，配接收头做遥控/避障",
           keywords=["红外", "发射", "遥控"]))

add(module("sd-card", "MicroSD 卡模块", 24.0, 18.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"),
            ("MOSI", "MOSI", "signal"), ("MISO", "MISO", "signal"), ("SCK", "SCK", "signal")],
           category="module", color="#1b3a63",
           features=[{"type": "grid", "x": 12.0, "y": 9.0, "r": 3.0, "rows": 1, "cols": 1}],
           doc="SPI 接法；仿真里只做占位，写入不会真的存文件",
           keywords=["sd卡", "存储", "spi"]))

add(module("rfid", "RC522 RFID 读卡器", 60.0, 40.0,
           [("VCC", "VCC", "power"), ("GND", "GND", "gnd"),
            ("SDA", "SDA", "signal"), ("SCK", "SCK", "signal"),
            ("MOSI", "MOSI", "signal"), ("MISO", "MISO", "signal")],
           category="module", color="#1b3a63", pin_edge="left",
           features=[{"type": "grid", "x": 34.0, "y": 20.0, "r": 12.0, "rows": 3, "cols": 3}],
           doc="SPI 读卡；仿真里暂为占位（不会返回 UID）",
           keywords=["rfid", "rc522", "刷卡"]))

MODULE_LIST = list(MODULES.values())


def get_module(mid):
    return MODULES.get(mid)

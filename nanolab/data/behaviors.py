# -*- coding: utf-8 -*-
"""配件行为（真正参与仿真的部分）——与几何数据分离，方便以后加配件"""

from __future__ import annotations

import math

from ..engine.runtime import Device


class Base:
    """所有配件行为的基类"""

    def __init__(self, geo: dict, uid: str):
        self.geo = geo
        self.id = uid
        self.name = geo.get("name", geo["id"])
        self.w = geo.get("w", 20)
        self.h = geo.get("h", 20)
        self.props = dict(geo.get("props") or {})
        for c in geo.get("controls") or []:
            self.props.setdefault(c["key"], c.get("value"))
        self.state: dict = {"burned": False}
        self.rt = None
        self.burned = False
        self.current = 0.0

    # ---- 电路元件接口（电阻这类「串联件」实现） ----
    is_series = False

    def other_pin(self, pin):
        return None

    def resistance(self):
        return float("inf")

    def carry_current(self, amps):
        pass

    # UI 改参数
    def on_prop(self, key, value):
        self.props[key] = value
        self.tick_controls()

    def tick_controls(self):
        pass

    # 引脚回调（默认忽略串联阻值/电源电压参数）
    def on_pin(self, pin, value, series_r=0.0, vcc=5.0, path_res=None):
        pass

    def digital_read(self, pin):
        return None

    def analog_read(self, pin):
        return None

    def device(self, kind=None):
        return None

    def update(self, rt, dt):
        pass

    # 串口/状态提示
    def log(self, rt, text):
        rt.serial_out.put("[%s] %s" % (self.name, text))


# ------------------------------------------------------------------ 简单器件
class Led(Base):
    """LED：有额定电压（Vf）和额定电流（20mA）。
    直连 5V → 电流远超 30mA → 必烧；
    串电阻后电流正常 → 只按「实际电压 / 额定电压」判断是否过压烧毁。"""

    COLORS = {"red": (255, 60, 60), "green": (60, 220, 90), "blue": (70, 140, 255),
              "yellow": (255, 210, 60), "white": (240, 245, 255)}
    VF = {"red": 2.0, "green": 2.1, "blue": 3.0, "yellow": 2.0, "white": 3.0}
    I_RATED = 0.020           # 额定电流 20mA
    I_MAX = 0.030             # 30mA 以上必烧
    R_INTERNAL = 12.0

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.level = 0
        self.current = 0.0
        self.props.setdefault("rated_v", None)
        self.props.setdefault("watts", 0.5)     # 小灯泡额定功率 0.5W
        self.state = {"level": 0, "burned": False, "current": 0.0}

    def on_pin(self, pin, value, series_r=0.0, vcc=5.0, path_res=None):
        if self.burned or pin != "A":
            return
        if not value:
            self.level = 0
            self.current = 0.0
            self.state["level"] = 0
            self.state["current"] = 0.0
            return
        vf = self.VF.get(self.props.get("color") or "red", 2.0)
        vcc = float(vcc)
        r_total = max(1.0, series_r + self.R_INTERNAL)
        amps = max(0.0, (vcc - vf) / r_total)
        self.current = amps
        self.state["current"] = amps
        for r in path_res or []:
            r.carry_current(amps)

        # ① 过压：施加电压 / 额定电压（灯有「额定电压」属性，缺省用灯珠 Vf）
        rated_v = float(self.props.get("rated_v") or vf)
        v_ratio = vcc / max(0.5, rated_v)
        # ② 过流：只有在「没超压」时才用电流判据（避免 5V 灯接 6V 被内阻过流误判成必烧）
        i_ratio = amps / self.I_RATED if v_ratio <= 1.0 else 0.0
        # 过功率：P = Vcc × I（小灯泡额定 0.5W）
        p_ratio = (vcc * amps) / float(self.props.get("watts") or 0.5)
        # 没串限流电阻时才算浪涌电流；串了电阻就按「过压」和「过功率」判
        in_rush = series_r <= 1.0
        worst = max(v_ratio, p_ratio, i_ratio if in_rush else 0.0)
        if worst > 1.0 and self.rt is not None:
            reason = []
            if i_ratio > 1.0:
                reason.append("%.0fmA（额定 20mA，%.1f 倍）" % (amps * 1000, i_ratio))
            if v_ratio > 1.0:
                reason.append("%.1fV 加到 %.1fV 的灯上（%.1f 倍）" % (vcc, rated_v, v_ratio))
            if p_ratio > 1.0:
                reason.append("功率 %.2fW / 额定 0.5W" % (vcc * amps))
            if self.rt._roll(self, worst, "、".join(reason)):
                self.level = 0
                self.state["level"] = 0
                return

        bright = min(1.0, amps / 0.018)
        self.level = max(1, int(255 * bright))
        self.state["level"] = self.level

    @property
    def color(self):
        return self.COLORS.get(self.props.get("color") or "red", (255, 60, 60))


class Resistor(Base):
    """电阻：串联件，阻值可调；功率超过 0.25W 会烧"""

    is_series = True
    RATING_W = 0.25

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"ohms": int(self.props.get("ohms", 220)), "burned": False}

    def other_pin(self, pin):
        return "2" if pin == "1" else "1"

    def resistance(self):
        if self.burned:
            return float("inf")
        return max(1.0, float(self.props.get("ohms") or 220))

    def on_prop(self, key, value):
        super().on_prop(key, value)
        if key == "ohms":
            self.state["ohms"] = int(value)

    def carry_current(self, amps):
        if self.burned or amps <= 0:
            return
        r = self.resistance()
        watts = amps * amps * r
        self.state["watts"] = watts
        if watts > self.RATING_W and self.rt is not None:
            self.rt._roll(self, watts / self.RATING_W,
                          "功率 %.2fW / 额定 0.25W（%.1f 倍）" % (watts, watts / self.RATING_W),
                          k="power")


class RgbLed(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.r = self.g = self.b = 0
        self.state = {"rgb": (0, 0, 0)}

    def on_pin(self, pin, value):
        v = int(value) if isinstance(value, int) else (255 if value else 0)
        if pin == "R":
            self.r = v
        elif pin == "G":
            self.g = v
        elif pin == "B":
            self.b = v
        self.state["rgb"] = (self.r, self.g, self.b)


class Button(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.pressed = False
        self.state = {"pressed": False}

    def on_prop(self, key, value):
        super().on_prop(key, value)
        if key == "pressed":
            self.pressed = bool(value)
            self.state["pressed"] = self.pressed

    def digital_read(self, pin):
        if pin == "OUT":
            return 1 if self.pressed else 0
        return None


class Pot(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"pct": 50}

    def analog_read(self, pin):
        if pin == "WIPER":
            return int(float(self.props.get("value") or 0) * 1023 / 100)
        return None

    def update(self, rt, dt):
        self.state["pct"] = float(self.props.get("value") or 0)


class AnalogSensor(Base):
    """通用模拟量传感器：靠一个 value 映射到 0..1023"""

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"pct": 0}

    def analog_read(self, pin):
        if pin in ("AO", "OUT", "SIG"):
            return self._value()
        return None

    def _value(self):
        return 0

    def digital_read(self, pin):
        return None


class Ldr(AnalogSensor):
    def _value(self):
        lux = float(self.props.get("lux", 300))
        return int(min(1023, max(0, (1 - min(lux, 1000) / 1000.0) * 1023)))

    def update(self, rt, dt):
        self.state["pct"] = self._value() / 1023 * 100


class Flame(AnalogSensor):
    def _value(self):
        return int(float(self.props.get("level", 10)) * 10.23)


class Soil(AnalogSensor):
    def _value(self):
        return int(float(self.props.get("moisture", 45)) * 10.23)


class Rain(AnalogSensor):
    def _value(self):
        return int(float(self.props.get("rain", 0)) * 10.23)


class Mq2(AnalogSensor):
    def _value(self):
        return int(min(1023, float(self.props.get("smoke", 120)) * 1.023))


class Sound(AnalogSensor):
    def _value(self):
        return int(float(self.props.get("level", 30)) * 10.23)


class Joystick(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"x": 50, "y": 50, "sw": False}

    def analog_read(self, pin):
        if pin == "X":
            return int(float(self.props.get("x", 50)) * 10.23)
        if pin == "Y":
            return int(float(self.props.get("y", 50)) * 10.23)
        return None

    def digital_read(self, pin):
        if pin == "SW":
            return 0 if self.props.get("sw") else 1
        return None

    def update(self, rt, dt):
        self.state = {"x": float(self.props.get("x", 50)), "y": float(self.props.get("y", 50)),
                      "sw": bool(self.props.get("sw"))}


class Pir(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.active_until = 0.0
        self.state = {"motion": False}

    def update(self, rt, dt):
        if self.props.get("motion"):
            self.active_until = max(self.active_until, rt.virtual_ms() + 2000)
        self.state["motion"] = rt.virtual_ms() < self.active_until

    def digital_read(self, pin):
        if pin == "OUT":
            return 1 if self.state.get("motion") else 0
        return None


class Button4(Base):
    """交通灯/多灯：这里给交通灯单独实现"""
    pass


class TrafficLight(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"r": False, "y": False, "g": False}

    def on_pin(self, pin, value):
        v = bool(value)
        if pin in ("R", "Y", "G"):
            self.state[pin.lower()] = v


class Fan(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.speed = 0
        self.state = {"speed": 0}

    def on_pin(self, pin, value):
        if pin == "+":
            self.speed = int(value)
            self.state["speed"] = self.speed


class VibrationMotor(Fan):
    pass


class Laser(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.on = False
        self.state = {"on": False}

    def on_pin(self, pin, value):
        if pin == "+":
            self.on = bool(value)
            self.state["on"] = self.on


class Relay(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.closed = False
        self.state = {"closed": False, "clicks": 0}

    def on_pin(self, pin, value):
        if pin != "IN":
            return
        active = bool(value)
        if not self.props.get("active_high", True):
            active = not active
        if active != self.closed:
            self.state["clicks"] = self.state.get("clicks", 0) + 1
        self.closed = active
        self.state["closed"] = active


class Buzzer(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.on = False
        self.freq = 0
        self.state = {"on": False, "freq": 0, "active": geo["id"] == "buzzer-active"}
        self._dev = _BuzzerDev(self)

    def on_pin(self, pin, value):
        if pin != "+":
            return
        if self.geo["id"] == "buzzer-active":
            self.on = bool(value)
            self.freq = 2300 if self.on else 0
            self.state.update(on=self.on, freq=self.freq)

    def device(self, kind=None):
        return self._dev if (kind in (None, "buzzer")) else None


class _BuzzerDev(Device):
    kind = "buzzer"

    def __init__(self, parent):
        self.p = parent

    def tone(self, freq):
        self.p.on = True
        self.p.freq = int(freq)
        self.p.state.update(on=True, freq=self.p.freq)

    def no_tone(self):
        self.p.on = False
        self.p.state.update(on=False, freq=0)


class Servo(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.angle = 90.0
        self.state = {"angle": 90.0}
        self._dev = _ServoDev(self)

    def device(self, kind=None):
        return self._dev if (kind in (None, "servo")) else None


class _ServoDev(Device):
    kind = "servo"

    def __init__(self, parent):
        self.p = parent

    def set_angle(self, deg):
        self.p.angle = max(0.0, min(180.0, float(deg)))
        self.p.state["angle"] = self.p.angle


class Stepper(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.phase = 0
        self.steps = 0
        self.state = {"phase": 0, "steps": 0}

    def on_pin(self, pin, value):
        if pin.startswith("IN") and value:
            self.phase = (self.phase + 1) % 4
            self.steps += 1
            self.state.update(phase=self.phase, steps=self.steps)


class Motor(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.speed = 0
        self.dir = 0
        self.state = {"speed": 0, "dir": 0}
        self._in1 = self._in2 = 0
        self._ena = 0

    def on_pin(self, pin, value):
        if pin == "IN1":
            self._in1 = int(value) if isinstance(value, int) else (1 if value else 0)
        elif pin == "IN2":
            self._in2 = int(value) if isinstance(value, int) else (1 if value else 0)
        elif pin == "ENA":
            self._ena = int(value) if isinstance(value, int) else (255 if value else 0)
        self.dir = (1 if self._in1 else 0) - (1 if self._in2 else 0)
        if not self.props.get("reverse", False):
            self.dir = -self.dir
        self.speed = self._ena if self.dir else 0
        self.state.update(speed=self.speed, dir=self.dir)


# ------------------------------------------------------------------ 传感器（库设备）
class DhtSensor(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self._dev = _DhtDev(self)
        self.state = {"temp": 25.0, "humi": 55.0}

    def device(self, kind=None):
        return self._dev if (kind in (None, "dht")) else None

    def update(self, rt, dt):
        self.state["temp"] = float(self.props.get("temp", 25))
        self.state["humi"] = float(self.props.get("humi", 55))


class _DhtDev(Device):
    kind = "dht"

    def __init__(self, parent):
        self.p = parent

    @property
    def temperature(self):
        return float(self.p.props.get("temp", 25))

    @property
    def humidity(self):
        return float(self.p.props.get("humi", 55))

    def begin(self):
        return True


class Ds18b20(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self._dev = _DsDev(self)
        self.state = {"temp": 26.0}

    def device(self, kind=None):
        return self._dev if (kind in (None, "ds18b20", "onewire")) else None

    def update(self, rt, dt):
        self.state["temp"] = float(self.props.get("temp", 26))


class _DsDev(Device):
    kind = "ds18b20"

    def __init__(self, parent):
        self.p = parent

    @property
    def temperature(self):
        return float(self.p.props.get("temp", 26))


class Ultrasonic(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.trig_at = None
        self.echo_ms = 0.0
        self.state = {"dist": 100.0, "echo": False}

    def on_pin(self, pin, value):
        if pin == "TRIG" and value:
            self.trig_at = _now_us()
            dist = float(self.props.get("dist", 100))
            self.echo_ms = dist * 0.058   # 58µs/cm

    def digital_read(self, pin):
        if pin != "ECHO":
            return None
        if self.trig_at is None:
            return 0
        dt_us = _now_us() - self.trig_at
        return 1 if 0 <= dt_us <= self.echo_ms * 1000.0 else 0

    def update(self, rt, dt):
        self.state["dist"] = float(self.props.get("dist", 100))
        self.state["echo"] = bool(self.trig_at is not None and
                                  (_now_us() - self.trig_at) <= self.echo_ms * 1000.0)


_T0 = None


def _now_us():
    import time
    global _T0
    if _T0 is None:
        _T0 = time.perf_counter()
    return (time.perf_counter() - _T0) * 1_000_000


class IrReceiver(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.pending = 0
        self.state = {"last": 0}

    def on_prop(self, key, value):
        super().on_prop(key, value)
        if key == "send" and value:
            self.pending = 0x00FFA25D     # 常见 NEC 键码
            self.state["last"] = self.pending
            self.props["send"] = False

    def device(self, kind=None):
        return _IrDev(self) if (kind in (None, "ir")) else None


class _IrDev(Device):
    kind = "ir"

    def __init__(self, parent):
        self.p = parent

    def take(self):
        c = self.p.pending
        self.p.pending = 0
        return c


# ------------------------------------------------------------------ 显示设备
class Oled(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.width = 128
        self.height = 64
        self.ops = []          # [("text", x, y, size, s)]
        self.state = {"ops": self.ops, "invert": False, "dirty": 0}
        self._dev = _OledDev(self)

    def device(self, kind=None):
        return self._dev if (kind in (None, "display")) else None

    def update(self, rt, dt):
        self.state["invert"] = bool(self.props.get("invert"))


class _OledDev(Device):
    kind = "display"

    def __init__(self, parent):
        self.p = parent
        self.width = 128
        self.height = 64

    def clear(self):
        self.p.ops.clear()
        self.p.state["dirty"] = self.p.state.get("dirty", 0) + 1

    def text(self, x, y, size, s):
        self.p.ops.append(("text", float(x), float(y), int(size), str(s)))

    def pixel(self, x, y, color=1):
        self.p.ops.append(("px", float(x), float(y), 1, int(color)))

    def line(self, x0, y0, x1, y1, color=1):
        self.p.ops.append(("line", float(x0), float(y0), float(x1), float(y1)))

    def rect(self, x, y, w, h, color=1):
        self.p.ops.append(("rect", float(x), float(y), float(w), float(h)))

    def fill_rect(self, x, y, w, h, color=1):
        self.p.ops.append(("frect", float(x), float(y), float(w), float(h)))

    def circle(self, x, y, r, color=1, fill=False):
        self.p.ops.append(("circle", float(x), float(y), float(r), fill))

    def flush(self):
        self.p.state["dirty"] = self.p.state.get("dirty", 0) + 1


class Lcd1602(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.cols, self.rows = 16, 2
        self.lines = [" " * 16, " " * 16]
        self.backlight = True
        self.state = {"lines": self.lines, "backlight": True}
        self._dev = _LcdDev(self)

    def device(self, kind=None):
        return self._dev if (kind in (None, "lcd")) else None

    def update(self, rt, dt):
        self.backlight = bool(self.props.get("backlight", True))
        self.state["backlight"] = self.backlight


class _LcdDev(Device):
    kind = "lcd"

    def __init__(self, parent):
        self.p = parent
        self.cols, self.rows = 16, 2

    def clear(self):
        self.p.lines = [" " * 16 for _ in range(2)]
        self.p.state["lines"] = self.p.lines

    def write(self, col, row, s):
        if row < 0 or row >= 2:
            return
        line = list(self.p.lines[row])
        for i, ch in enumerate(s):
            c = col + i
            if 0 <= c < 16:
                line[c] = ch
        self.p.lines[row] = "".join(line)
        self.p.state["lines"] = self.p.lines


class Tm1637(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.digits = [0, 0, 0, 0]
        self.dots = False
        self.brightness = 5
        self.state = {"digits": list(self.digits), "dots": False}
        self._dev = _TmDev(self)

    def device(self, kind=None):
        return self._dev if (kind in (None, "tm1637")) else None

    def update(self, rt, dt):
        self.brightness = int(self.props.get("brightness", 5) or 5)


class _TmDev(Device):
    kind = "tm1637"

    def __init__(self, parent):
        self.p = parent

    def set_segments(self, segs, pos=0):
        for i, seg in enumerate(segs):
            idx = pos + i
            if 0 <= idx < 4:
                self.p.digits[idx] = seg
        self.p.state["digits"] = list(self.p.digits)

    def set_number(self, num, length=4, pos=0, dots=False):
        s = str(abs(int(num))).rjust(length, " ")[:length]
        digits = []
        for ch in s:
            digits.append(int(ch) if ch.isdigit() else 0x7F)
        for i in range(4):
            self.p.digits[i] = digits[i] if i < len(digits) else 0
        self.p.dots = bool(dots)
        self.p.state.update(digits=list(self.p.digits), dots=self.p.dots)


class NeoPixelRing(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        n = 8
        for f in geo.get("features") or []:
            if f.get("type") == "ring":
                n = int(f.get("n", 8))
        self.num = n
        self.pixels = [(0, 0, 0)] * n
        self.brightness = 1.0
        self.state = {"pixels": self.pixels}
        self._dev = _NeoDev(self)

    def device(self, kind=None):
        return self._dev if (kind in (None, "neopixel")) else None


class _NeoDev(Device):
    kind = "neopixel"

    def __init__(self, parent):
        self.p = parent
        self.num = parent.num
        self.pixels = parent.pixels
        self.brightness = 1.0

    def resize(self, n):
        self.num = int(n)
        self.p.num = int(n)
        self.p.pixels = [(0, 0, 0)] * int(n)
        self.p.state["pixels"] = self.p.pixels
        self.pixels = self.p.pixels

    def set_pixel(self, i, color):
        if 0 <= int(i) < len(self.p.pixels):
            b = getattr(self, "brightness", 1.0)
            self.p.pixels[int(i)] = tuple(int(c * b) for c in color)
            self.p.state["pixels"] = self.p.pixels

    def show(self):
        self.p.state["pixels"] = self.p.pixels


class Breadboard(Base):
    pass


class PowerModule(Base):
    pass


class Hc05(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"note": ""}

    def on_prop(self, key, value):
        super().on_prop(key, value)
        if key == "send" and value:
            self.props["send"] = False
            self.state["note"] = "发来: hello"


class Rtc(Base):
    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"t": "12:00:00"}

    def update(self, rt, dt):
        ms = int(rt.virtual_ms() / 1000)
        self.state["t"] = "%02d:%02d:%02d" % ((ms // 3600) % 24, (ms // 60) % 60, ms % 60)


class DigitalIn(Base):
    """通用数字输入件：开关/霍尔/倾斜/干簧管/限位…用 props['state'] 控制"""

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.props.setdefault("state", False)
        self.state = {"on": bool(self.props.get("state"))}

    def on_prop(self, key, value):
        super().on_prop(key, value)
        if key == "state":
            self.state["on"] = bool(value)

    def digital_read(self, pin):
        return 1 if self.props.get("state") else 0

    def update(self, rt, dt):
        self.state["on"] = bool(self.props.get("state"))


class AnalogIn(Base):
    """通用模拟输入：一个滑块 → 0..1023，按 key 取值"""

    KEY = "value"
    MAX = 1023.0

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"pct": 0.0}

    def analog_read(self, pin):
        return int(min(1023, max(0, float(self.props.get(self.KEY, 0)) / self.MAX * 1023)))

    def update(self, rt, dt):
        self.state["pct"] = float(self.props.get(self.KEY, 0)) / self.MAX * 100.0


class Lm35(AnalogIn):
    KEY = "temp"
    MAX = 100.0


class Acs712(AnalogIn):
    KEY = "amps"
    MAX = 30.0


class OnOff(Base):
    """开关型执行器：水泵/电磁锁/红外发射灯"""

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.on = False
        self.state = {"on": False}

    def on_pin(self, pin, value, series_r=0.0, vcc=5.0, path_res=None):
        if pin in ("+", "IN", "SIG", "A"):
            self.on = bool(value)
            self.state["on"] = self.on


class StubDevice(Base):
    """没仿真实现但有 device 接口的模块（SD 卡/RFID 等）"""

    def __init__(self, geo, uid):
        super().__init__(geo, uid)
        self.state = {"note": ""}

    def device(self, kind=None):
        class _D(Device):
            kind = "stub"

            def __init__(self, parent):
                self.p = parent

            def __getattr__(self, item):
                def _noop(*a, **k):
                    return 0
                return _noop

        return _D(self)


BEHAVIORS = {
    "led": Led,
    "resistor": Resistor,
    "rgb-led": RgbLed,
    "button-module": Button,
    "potentiometer": Pot,
    "ldr": Ldr,
    "flame-sensor": Flame,
    "soil-moisture": Soil,
    "rain-sensor": Rain,
    "mq2": Mq2,
    "sound-sensor": Sound,
    "joystick": Joystick,
    "pir": Pir,
    "hc-sr04": Ultrasonic,
    "ir-receiver": IrReceiver,
    "dht11": DhtSensor,
    "dht22": DhtSensor,
    "ds18b20": Ds18b20,
    "encoder": Pot,           # 暂按电位器处理转动量
    "ssd1306-oled": Oled,
    "lcd1602-i2c": Lcd1602,
    "tm1637": Tm1637,
    "max7219": Oled,
    "ws2812-ring": NeoPixelRing,
    "buzzer-active": Buzzer,
    "buzzer-passive": Buzzer,
    "relay-1ch": Relay,
    "servo-sg90": Servo,
    "stepper-28byj": Stepper,
    "motor-l298n": Motor,
    "traffic-light": TrafficLight,
    "fan": Fan,
    "vibration-motor": VibrationMotor,
    "laser": Laser,
    "breadboard-400": Breadboard,
    "power-module": PowerModule,
    "hc05": Hc05,
    "rtc": Rtc,
    "hall-switch": DigitalIn,
    "tilt-switch": DigitalIn,
    "reed-switch": DigitalIn,
    "limit-switch": DigitalIn,
    "ttp223": DigitalIn,
    "button-bare": DigitalIn,
    "ir-pair": DigitalIn,
    "lm35": Lm35,
    "acs712": Acs712,
    "water-pump": OnOff,
    "solenoid": OnOff,
    "ir-led": OnOff,
    "sd-card": StubDevice,
    "rfid": StubDevice,
}


def make_behavior(geo: dict, uid: str):
    cls = BEHAVIORS.get(geo.get("behavior") or geo["id"], Base)
    return cls(geo, uid)

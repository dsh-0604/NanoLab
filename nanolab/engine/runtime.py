# -*- coding: utf-8 -*-
"""
runtime.py —— 硬件仿真内核（纯 Python，不依赖 Qt，可单独测试）

模型：
  - 一块开发板：引脚表、逻辑电平、ADC 位数
  - 若干配件：各自实现 on_pin / digital_read / analog_read / device()
  - 接线表：[(板子引脚, 配件id, 配件引脚)]
  - 用户代码在**独立线程**里跑：setup() 一次，loop() 反复
  - delay() 按虚拟速度 sleep，所以界面不会卡，时间也不会飞掉

库垫片（DHT / Servo / SSD1306 / LCD1602 / NeoPixel / TM1637 / OneWire…）
把调用转给对应配件暴露的 device 对象。
"""

from __future__ import annotations

import math
import queue
import threading
import time
import traceback

from . import xlate


# --------------------------------------------------------------------------- 小工具
class Buf:
    """模拟 char buf[N]"""

    def __init__(self, n):
        self.data = [0] * int(n)

    def __setitem__(self, i, v):
        if 0 <= i < len(self.data):
            self.data[i] = int(v)

    def __getitem__(self, i):
        return self.data[i]

    def __len__(self):
        return len(self.data)

    def __str__(self):
        return "".join(chr(c) if c else "" for c in self.data).rstrip("\x00")

    def __repr__(self):
        return str(self)


class String(str):
    """Arduino String 的常用方法（Python str 已经够用，这里补几个同名方法）"""

    def c_str(self):
        return str(self)

    def toInt(self):
        try:
            return int(float(self))
        except Exception:
            return 0

    def toFloat(self):
        try:
            return float(self)
        except Exception:
            return 0.0

    def equals(self, other):
        return str(self) == str(other)

    def length(self):
        return len(self)

    def substring(self, a, b=None):
        return String(str(self)[a:b] if b is not None else str(self)[a:])


def fmt_num(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v:
            return "nan"
        if v in (float("inf"), float("-inf")):
            return "inf" if v > 0 else "-inf"
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        txt = ("%.3f" % v).rstrip("0").rstrip(".")
        return txt or "0"
    return str(v)


# --------------------------------------------------------------------------- 设备基类
class Device:
    kind = "device"


class Runtime:
    def __init__(self, board: dict):
        self.board = board
        self.pin_by_id: dict[str, dict] = {}
        self.alias: dict[str, str] = {}
        self.modules: list = []            # 配件实例（见 modules.py）
        # 连线：任意两个端点相连，端点是 ("b", 板子引脚) 或 ("m", 配件id, 配件引脚)
        self.links: list[tuple[tuple, tuple]] = []
        self.burn_probability = 100.0      # 过载时烧毁概率（%）
        self._nets: dict[tuple, int] = {}
        self._net_members: dict[int, list[tuple]] = {}
        self._build_pins(board)

        self.pin_state: dict[str, int] = {}
        self.pin_modes: dict[str, int] = {}

        self.speed = 1.0                 # 1 = 实时，2 = 2 倍速
        self.serial_out: "queue.Queue[str]" = queue.Queue()
        self._sbuf = ""
        self.serial_in: list[str] = []
        self.errors: "queue.Queue[str]" = queue.Queue()
        self.running = False
        self.thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.ns: dict = {}
        self.code = ""
        self._py_source = ""
        self._line_map: list[int] = []
        self._iter_since = 0
        self.started_at = 0.0
        self.tick_hooks = []              # 主线程注册：每帧回调（GUI 用）

    # ------------------------------------------------------------------ 引脚
    def _build_pins(self, board):
        pins = (board.get("pins") or [])
        for p in pins:
            self.pin_by_id[p["id"]] = p
            pid = p["id"]
            num = "".join(ch for ch in pid if ch.isdigit())
            if num:
                key = num
                cur = self.alias.get(key)
                if cur is None or self.pin_by_id.get(cur, {}).get("kind") == "analog":
                    self.alias[key] = pid
            if pid.startswith("A") and pid[1:].isdigit():
                self.alias["ADC" + pid[1:]] = pid

    def resolve_pin(self, name) -> str | None:
        if name is None:
            return None
        s = str(name)
        if s in self.pin_by_id:
            return s
        if s in self.alias:
            return self.alias[s]
        if s.isdigit():
            for cand in ("D" + s, "GPIO" + s, "GP" + s, "A" + s):
                if cand in self.pin_by_id:
                    return cand
        return None

    # ------------------------------------------------------------------ 网表
    def rebuild_nets(self):
        """并查集：把任意相连的引脚合并成同一个电网络"""
        parent: dict[tuple, tuple] = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for a, b in self.links:
            union(tuple(a), tuple(b))

        self._nets = {}
        self._net_members = {}
        idx = 0
        for node in list(parent.keys()):
            root = find(node)
            if root not in self._nets:
                self._nets[root] = idx
                self._net_members[idx] = []
                idx += 1
            nid = self._nets[root]
            self._nets[node] = nid
            self._net_members[nid].append(node)

    def net_of(self, endpoint) -> int | None:
        return self._nets.get(tuple(endpoint))

    def net_members(self, nid: int):
        return self._net_members.get(nid, [])

    def nets_of(self, board_pin: str):
        """兼容旧代码：返回该板子引脚所在网里的配件端点列表"""
        out = []
        nid = self.net_of(("b", board_pin))
        if nid is None:
            return out
        for ep in self.net_members(nid):
            if ep[0] == "m":
                out.append((board_pin, ep[1], ep[2]))
        return out

    def module_by_id(self, mid: str):
        for m in self.modules:
            if getattr(m, "id", None) == mid:
                return m
        return None

    def device_on(self, pin_name, kind=None):
        pid = self.resolve_pin(pin_name)
        if not pid:
            return None
        for bp, mid, mpin in self.nets_of(pid):
            m = self.module_by_id(mid)
            if m is None:
                continue
            dev = m.device(kind)
            if dev is not None and (kind is None or getattr(dev, "kind", None) == kind):
                return dev
        return None

    def device_any(self, kind):
        for m in self.modules:
            dev = m.device(kind)
            if dev is not None and getattr(dev, "kind", None) == kind:
                return dev
        return None

    # ------------------------------------------------------------------ IO
    def _pin(self, name):
        pid = self.resolve_pin(name)
        if pid is None:
            self.serial_out.put("[引脚] 板子上没有引脚 %s（检查接线或板子型号）" % name)
        return pid

    def pin_mode(self, pin, mode):
        pid = self._pin(pin)
        if pid:
            self.pin_modes[pid] = mode

    def digital_write(self, pin, value):
        pid = self._pin(pin)
        if not pid:
            return
        v = 1 if value else 0
        self.pin_state[pid] = v
        self.pin_modes[pid] = 1
        self._drive(pid, v)

    def digital_read(self, pin):
        pid = self._pin(pin)
        if not pid:
            return 0
        for _, mid, mpin in self.nets_of(pid):
            m = self.module_by_id(mid)
            if m is None or getattr(m, "burned", False):
                continue
            v = m.digital_read(mpin)
            if v is not None:
                return 1 if v else 0
        if self.pin_modes.get(pid) == 2:      # INPUT_PULLUP
            return 1
        return self.pin_state.get(pid, 0)

    def analog_read(self, pin):
        pid = self._pin(pin)
        if not pid:
            return 0
        bits = int((self.board.get("capabilities") or {}).get("analog_bits", 10))
        vmax = (1 << bits) - 1
        for _, mid, mpin in self.nets_of(pid):
            m = self.module_by_id(mid)
            if m is None or getattr(m, "burned", False):
                continue
            v = m.analog_read(mpin)
            if v is not None:
                return int(max(0, min(vmax, round(float(v) * vmax / 1023.0))))
        return 0

    def analog_write(self, pin, value):
        pid = self._pin(pin)
        if not pid:
            return
        v = max(0, min(255, int(value)))
        self.pin_state[pid] = v
        self.pin_modes[pid] = 1
        self._drive(pid, v)

    def _drive(self, board_pin, value):
        """把电平送进该引脚所在的网络；遇到电阻就继续往另一侧传（串联）"""
        nid = self.net_of(("b", board_pin))
        if nid is None:
            return
        pin_def = self.pin_by_id.get(board_pin) or {}
        if pin_def.get("kind") == "power":
            vcc = float(pin_def.get("voltage") or self.board.get("logic") or 5.0)
        else:
            vcc = float(self.board.get("logic") or 5.0)
        self._propagate(nid, value, 0.0, [], set(), vcc)

    def _propagate(self, nid, value, series_r, path_res, visited, vcc):
        if nid in visited:
            return
        visited = visited | {nid}
        for ep in self.net_members(nid):
            if ep[0] != "m":
                continue
            mid, mpin = ep[1], ep[2]
            m = self.module_by_id(mid)
            if m is None:
                continue
            if getattr(m, "is_series", False):
                # 电阻：把电平传到另一侧，累加阻值
                other = m.other_pin(mpin)
                if other is None:
                    continue
                onid = self.net_of(("m", mid, other))
                if onid is None or onid == nid:
                    continue
                self._propagate(onid, value, series_r + m.resistance(), path_res + [m], visited, vcc)
                continue
            try:
                m.on_pin(mpin, value, series_r=series_r, vcc=vcc, path_res=list(path_res))
            except TypeError:
                try:
                    m.on_pin(mpin, value)
                except Exception as e:
                    self.serial_out.put("[配件] %s 处理引脚出错：%s" % (getattr(m, "name", mid), e))
            except Exception as e:
                self.serial_out.put("[配件] %s 处理引脚出错：%s" % (getattr(m, "name", mid), e))


    # ------------------------------------------------------------------ 烧毁模型
    # 真实思路：器件有额定值，超出越多越容易烧；超一点点是概率性损坏，超很多是必烧。
    #   ratio = 实际值 / 额定值
    #   ratio <= BURN_MIN      → 不烧（容差 10%）
    #   BURN_MIN..BURN_HARD    → 概率按比例平方增长
    #   ratio >= BURN_HARD     → 100% 必烧
    BURN_HARD = 1.5
    BURN_MIN = 1.10

    def _burn_chance(self, ratio: float) -> float:
        if ratio <= self.BURN_MIN:
            return 0.0
        if ratio >= self.BURN_HARD:
            return 100.0
        t = (ratio - self.BURN_MIN) / (self.BURN_HARD - self.BURN_MIN)
        return min(100.0, (t ** 2) * 100.0)

    def _roll(self, module, ratio: float, reason: str, k: str = "voltage") -> bool:
        """按倍率掷骰子；返回是否真的烧毁"""
        import random
        if getattr(module, "burned", False):
            return False
        if getattr(self, "burn_probability", 100.0) <= 0.0:
            return False
        chance = self._burn_chance(ratio)
        module.stress = {**getattr(module, "stress", {}), k: round(ratio, 2),
                         "chance": round(chance, 1)}
        if chance <= 0:
            return False
        if random.random() * 100.0 >= chance:
            return False
        module.burned = True
        module.state["burned"] = True
        module.state["current"] = 0.0
        level = "必烧" if chance >= 100 else ("约 %d%% 概率烧了" % round(chance))
        self.serial_out.put("[烧毁] %s：%s（%s）" % (module.name, reason, level))
        return True

    def maybe_burn(self, module, reason: str, ratio: float = 999.0) -> bool:
        return self._roll(module, ratio, reason)


    def pulse_in(self, pin, state, timeout_us=1000000):
        pid = self._pin(pin)
        if not pid:
            return 0
        want = 1 if state else 0
        width = 0
        started = False
        steps = 0
        max_steps = min(int(timeout_us), 60000)
        while steps < max_steps:
            cur = 0
            for _, mid, mpin in self.nets_of(pid):
                m = self.module_by_id(mid)
                if m is None:
                    continue
                v = m.digital_read(mpin)
                if v is not None:
                    cur = 1 if v else 0
                    break
            if not started:
                if cur == want:
                    started = True
                    width = 0
            else:
                if cur == want:
                    width += 1
                else:
                    break
            steps += 1
        return width

    # ------------------------------------------------------------------ 串口
    def _serial(self):
        rt = self

        class _Serial:
            def _w(self, s):
                rt.serial_out.put(s)

            def begin(self, baud=115200, *a):
                rt.serial_out.put("[串口] 已打开 %s bps" % baud)

            def end(self, *a):
                pass

            def print(self, *args):
                rt._sbuf += "".join(fmt_num(a) for a in args)

            def println(self, *args):
                rt._sbuf += "".join(fmt_num(a) for a in args)
                self._w(rt._sbuf)
                rt._sbuf = ""

            def printf(self, fmt, *args):
                out = str(fmt)
                for a in args:
                    for f in ("%d", "%i", "%u", "%s", "%f", "%x", "%c"):
                        if f in out:
                            val = a
                            if f == "%s":
                                val = str(a)
                            elif f == "%c":
                                val = chr(int(a))
                            elif f == "%x":
                                val = format(int(a), "x")
                            out = out.replace(f, fmt_num(val), 1)
                            break
                self._w(out)

            def write(self, c):
                if isinstance(c, str):
                    chunk = c
                elif isinstance(c, (bytes, bytearray)):
                    chunk = bytes(c).decode("utf-8", "replace")
                else:
                    chunk = chr(int(c))
                rt._sbuf += chunk
                while "\n" in rt._sbuf:
                    line, rt._sbuf = rt._sbuf.split("\n", 1)
                    self._w(line.rstrip("\r"))

            def available(self):
                return len(rt.serial_in)

            def read(self):
                return ord(rt.serial_in.pop(0)) if rt.serial_in else -1

            def peek(self):
                return ord(rt.serial_in[0]) if rt.serial_in else -1

            def readString(self):
                s = "".join(rt.serial_in)
                rt.serial_in.clear()
                return String(s.rstrip("\r\n"))

            def readStringUntil(self, ch):
                out = []
                while rt.serial_in:
                    c = rt.serial_in.pop(0)
                    if c == ch:
                        break
                    out.append(c)
                return String("".join(out))

            def flush(self):
                pass

            def setTimeout(self, *a):
                pass

        return _Serial()

    # ------------------------------------------------------------------ 命名空间
    def _namespace(self, extra_pin_names=()):
        rt = self
        ns: dict = {
            "__builtins__": __builtins__,
            "HIGH": 1, "LOW": 0,
            "INPUT": 0, "OUTPUT": 1, "INPUT_PULLUP": 2,
            "LED_BUILTIN": (self.board.get("capabilities") or {}).get("builtin_led") or "D13",
            "PI": math.pi, "DEC": 10, "HEX": 16, "OCT": 8, "BIN": 2,
            "String": String,
            "Serial": self._serial(),
            "pinMode": self.pin_mode,
            "digitalWrite": self.digital_write,
            "digitalRead": self.digital_read,
            "analogRead": self.analog_read,
            "analogWrite": self.analog_write,
            "analogReadResolution": lambda *a: None,
            "analogWriteResolution": lambda *a: None,
            "delay": self.delay,
            "delayMicroseconds": lambda us: rt.delay(float(us) / 1000.0),
            "millis": lambda: int(rt.virtual_ms()),
            "micros": lambda: int(rt.virtual_ms() * 1000),
            "yield": lambda: None,
            "pulseIn": self.pulse_in,
            "tone": self.tone,
            "noTone": self.no_tone,
            "map": lambda x, a, b, c, d: (int((x - a) * (d - c) / (b - a)) + c) if b != a else c,
            "constrain": lambda x, a, b: a if x < a else (b if x > b else x),
            "randomSeed": lambda *a: None,
            "random": random_range,
            "abs": abs, "sqrt": math.sqrt, "pow": pow, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "atan2": math.atan2, "atan": math.atan, "exp": math.exp,
            "log": math.log, "log10": math.log10, "floor": math.floor, "ceil": math.ceil,
            "round": round, "fabs": math.fabs, "fmod": math.fmod, "min": min, "max": max,
            "sq": lambda x: x * x, "isnan": lambda x: x != x,
            "toRadians": math.radians, "toDegrees": math.degrees,
            "__mk_arr": lambda n: [0] * int(n),
            "__mk_buf": Buf,
            "__sizeof": lambda v: len(v) if hasattr(v, "__len__") else 4,
            "sprintf": sprintf,
            "dtostrf": lambda v, w, p: fmt_num(v),
            "__tick": lambda: None,
            "bitRead": lambda x, b: (int(x) >> b) & 1,
            "bitSet": lambda x, b: int(x) | (1 << b),
            "bitClear": lambda x, b: int(x) & ~(1 << b),
            "bitWrite": lambda x, b, v: (int(x) | (1 << b)) if v else (int(x) & ~(1 << b)),
            "lowByte": lambda x: int(x) & 0xFF,
            "highByte": lambda x: (int(x) >> 8) & 0xFF,
            "attachInterrupt": lambda *a: None,
            "detachInterrupt": lambda *a: None,
            "digitalPinToInterrupt": lambda p: p,
            "EEPROM": _EEPROM(),
            "Wire": _Wire(),
            "SPI": _SPI(),
            "WiFi": _Stub("WiFi", rt),
            "BLE": _Stub("BLE", rt),
            "ESP": _Stub("ESP", rt),
        }
        # 板子引脚名直接当变量用：GPIO8 / D13 / PA5 / A0
        for pid in self.pin_by_id:
            ns.setdefault(pid, pid)
        for alias_key, pid in self.alias.items():
            if alias_key.isidentifier() and not alias_key.isdigit():
                ns.setdefault(alias_key, pid)
        ns.update(self._library_shims())
        return ns

    # ------------------------------------------------------------------ 库垫片
    def _library_shims(self):
        rt = self

        class DHT:
            DHT11, DHT21, DHT22 = 11, 21, 22

            def __init__(self, pin, kind=22):
                self.pin = pin
                self.kind = kind

            def _dev(self):
                return rt.device_on(self.pin, "dht") or rt.device_any("dht")

            def begin(self, *a):
                return True

            def readTemperature(self, f=False):
                dev = self._dev()
                t = dev.temperature if dev else 25.0
                return t * 9 / 5 + 32 if f else t

            def readHumidity(self):
                dev = self._dev()
                return dev.humidity if dev else 60.0

            def read(self, *a):
                return True

            def computeHeatIndex(self, t, h, f=False):
                return t

        class OneWire:
            def __init__(self, pin):
                self.pin = pin

            def reset(self):
                return 1

            def skip(self):
                pass

            def write(self, *a):
                pass

            def read(self):
                return 0

        class DallasTemperature:
            def __init__(self, wire=None):
                self.wire = wire

            def begin(self, *a):
                return True

            def requestTemperatures(self, *a):
                pass

            def getTempCByIndex(self, i=0):
                dev = rt.device_any("ds18b20")
                return dev.temperature if dev else 25.0

            def getTempFByIndex(self, i=0):
                return self.getTempCByIndex(i) * 9 / 5 + 32

            def getDeviceCount(self):
                return 1

            def setResolution(self, *a):
                pass

        class Servo:
            def __init__(self):
                self.pin = None
                self.angle = 90

            def attach(self, pin, *a):
                self.pin = pin
                return 1

            def _dev(self):
                return (rt.device_on(self.pin, "servo") if self.pin is not None
                        else None) or rt.device_any("servo")

            def write(self, deg):
                self.angle = float(deg)
                dev = self._dev()
                if dev:
                    dev.set_angle(self.angle)

            def writeMicroseconds(self, us):
                self.write(max(0, min(180, (us - 500) * 180 / 2000)))

            def read(self):
                return self.angle

            def detach(self):
                self.pin = None

            def attached(self):
                return self.pin is not None

        class Adafruit_NeoPixel:
            def __init__(self, n, pin=None, kind=0):
                self.n = int(n)
                self.pin = pin

            def _dev(self):
                return ((rt.device_on(self.pin, "neopixel") if self.pin is not None else None)
                        or rt.device_any("neopixel"))

            def begin(self):
                dev = self._dev()
                if dev:
                    dev.resize(self.n)
                return True

            def Color(self, r, g, b):
                return (int(r) & 255) << 16 | (int(g) & 255) << 8 | (int(b) & 255)

            def setPixelColor(self, i, *args):
                dev = self._dev()
                if not dev:
                    return
                if len(args) >= 3:
                    c = (int(args[0]), int(args[1]), int(args[2]))
                else:
                    v = int(args[0])
                    c = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
                dev.set_pixel(int(i), c)

            def setBrightness(self, v):
                dev = self._dev()
                if dev:
                    dev.brightness = int(v) / 255.0

            def fill(self, color, first=0, count=None):
                dev = self._dev()
                if not dev:
                    return
                if isinstance(color, int):
                    c = ((color >> 16) & 255, (color >> 8) & 255, color & 255)
                else:
                    c = color
                n = dev.num if count is None else int(count)
                for i in range(int(first), int(first) + n):
                    dev.set_pixel(i, c)

            def clear(self):
                self.fill(0)

            def show(self):
                dev = self._dev()
                if dev:
                    dev.show()

            def numPixels(self):
                return self.n

        class Gfx:
            def __init__(self, w, h):
                self._w, self._h = int(w), int(h)
                self._cx = self._cy = 0
                self._size = 1
                self._color = 1

            def _dev(self):
                return rt.device_any("display")

            def width(self):
                return self._w

            def height(self):
                return self._h

            def begin(self, *a):
                dev = self._dev()
                if dev:
                    dev.width, dev.height = self._w, self._h
                return True

            def clearDisplay(self):
                dev = self._dev()
                if dev:
                    dev.clear()

            def fillScreen(self, color=0):
                dev = self._dev()
                if dev:
                    dev.clear()

            def display(self):
                dev = self._dev()
                if dev:
                    dev.flush()

            def setCursor(self, x, y):
                self._cx, self._cy = int(x), int(y)

            def setTextSize(self, s):
                self._size = max(1, int(s))

            def setTextColor(self, c, bg=None):
                self._color = int(c)

            def print(self, *args):
                dev = self._dev()
                if not dev:
                    return
                text = "".join(fmt_num(a) for a in args)
                dev.text(self._cx, self._cy, self._size, text)
                self._cx += int(len(text) * 6 * self._size)

            def println(self, *args):
                dev = self._dev()
                if not dev:
                    return
                text = "".join(fmt_num(a) for a in args)
                dev.text(self._cx, self._cy, self._size, text)
                self._cx = 0
                self._cy += 8 * self._size

            def drawPixel(self, x, y, color=1):
                dev = self._dev()
                if dev:
                    dev.pixel(x, y, color)

            def drawLine(self, x0, y0, x1, y1, color=1):
                dev = self._dev()
                if dev:
                    dev.line(x0, y0, x1, y1, color)

            def drawRect(self, x, y, w, h, color=1):
                dev = self._dev()
                if dev:
                    dev.rect(x, y, w, h, color)

            def fillRect(self, x, y, w, h, color=1):
                dev = self._dev()
                if dev:
                    dev.fill_rect(x, y, w, h, color)

            def drawCircle(self, x, y, r, color=1):
                dev = self._dev()
                if dev:
                    dev.circle(x, y, r, color)

            def fillCircle(self, x, y, r, color=1):
                dev = self._dev()
                if dev:
                    dev.circle(x, y, r, color, True)

            def startscrollright(self, *a):
                pass

            def stopscroll(self, *a):
                pass

            def invertDisplay(self, *a):
                pass

            def cp437(self, *a):
                return True

            def setTextWrap(self, *a):
                pass

            def drawBitmap(self, *a):
                pass

        class SSD1306(Gfx):
            def __init__(self, w=128, h=64, *args, **kwargs):
                super().__init__(w, h)

        class TFT(Gfx):
            def __init__(self, w=160, h=128, *args, **kwargs):
                super().__init__(w, h)

        class LiquidCrystal_I2C:
            def __init__(self, addr=0x27, cols=16, rows=2):
                self.cols, self.rows = int(cols), int(rows)
                self._cx = self._cy = 0

            def _dev(self):
                return rt.device_any("lcd")

            def begin(self, *a):
                dev = self._dev()
                if dev:
                    dev.cols, dev.rows = self.cols, self.rows
                return True

            def init(self, *a):
                pass

            def backlight(self, *a):
                dev = self._dev()
                if dev:
                    dev.backlight = True

            def noBacklight(self, *a):
                dev = self._dev()
                if dev:
                    dev.backlight = False

            def clear(self):
                dev = self._dev()
                if dev:
                    dev.clear()

            def home(self):
                self._cx = self._cy = 0

            def setCursor(self, c, r):
                self._cx, self._cy = int(c), int(r)

            def print(self, *args):
                dev = self._dev()
                if not dev:
                    return
                s = "".join(fmt_num(a) for a in args)
                dev.write(self._cx, self._cy, s)
                self._cx += len(s)

            def println(self, *args):
                self.print(*args)
                self._cx = 0
                self._cy += 1

            def createChar(self, *a):
                pass

            def display(self, *a):
                pass

            def noDisplay(self, *a):
                pass

            def scrollDisplayLeft(self, *a):
                pass

            def scrollDisplayRight(self, *a):
                pass

        class TM1637Display:
            def __init__(self, clk=None, dio=None):
                self._b = 7

            def _dev(self):
                return rt.device_any("tm1637")

            def setBrightness(self, b, *a):
                dev = self._dev()
                if dev:
                    dev.brightness = int(b)

            def setSegments(self, segs, pos=0, length=4):
                dev = self._dev()
                if dev:
                    dev.set_segments(list(segs), int(pos))

            def showNumberDec(self, num, leading=False, length=4, pos=0, dots=0):
                dev = self._dev()
                if dev:
                    dev.set_number(int(num), int(length), int(pos), bool(dots))

            def showNumberDecEx(self, num, dots=0, leading=False, length=4, pos=0):
                self.showNumberDec(num, leading, length, pos, dots)

            def clear(self):
                dev = self._dev()
                if dev:
                    dev.set_number(0, 4, 0, False)

        class IRrecv:
            def __init__(self, pin=None, *a):
                self.pin = pin

            def _dev(self):
                return ((rt.device_on(self.pin, "ir") if self.pin is not None else None)
                        or rt.device_any("ir"))

            def enableIRIn(self, *a):
                pass

            def disableIRIn(self, *a):
                pass

            def decode(self, results=None):
                dev = self._dev()
                if not dev:
                    return 0
                code = dev.take()
                if not code:
                    return 0
                if results is not None:
                    try:
                        results.value = code
                    except Exception:
                        pass
                return 1

            def resume(self, *a):
                pass

        class _JsonStub:
            def __init__(self, *a, **k):
                self.data = {}

            def __getitem__(self, k):
                return self.data.setdefault(k, _JsonStub())

            def __setitem__(self, k, v):
                self.data[k] = v

        shims = {
            "DHT": DHT,
            "DHT11": 11, "DHT21": 21, "DHT22": 22,
            "OneWire": OneWire,
            "DallasTemperature": DallasTemperature,
            "Servo": Servo,
            "Adafruit_NeoPixel": Adafruit_NeoPixel,
            "NEO_GRB": 1, "NEO_RGB": 2, "NEO_KHZ800": 1,
            "Adafruit_SSD1306": SSD1306,
            "Adafruit_GFX": Gfx,
            "Adafruit_ST7735": TFT,
            "Adafruit_ILI9341": TFT,
            "SSD1306_SWITCHCAPVCC": 2, "SSD1306_EXTERNALVCC": 1,
            "WHITE": 1, "BLACK": 0, "SSD1306_WHITE": 1, "SSD1306_BLACK": 0,
            "LiquidCrystal_I2C": LiquidCrystal_I2C,
            "LiquidCrystal": LiquidCrystal_I2C,
            "TM1637Display": TM1637Display,
            "SEG_A": 1, "SEG_B": 2, "SEG_C": 4, "SEG_D": 8, "SEG_E": 16,
            "SEG_F": 32, "SEG_G": 64, "SEG_DP": 128,
            "IRrecv": IRrecv,
            "DynamicJsonDocument": _JsonStub,
            "StaticJsonDocument": _JsonStub,
            "deserializeJson": lambda doc, text: 0,
            "serializeJson": lambda doc: String("{}"),
        }
        return shims

    # ------------------------------------------------------------------ 虚拟时间
    def delay(self, ms):
        if not self.running:
            return
        ms = float(ms or 0)
        if ms > 0:
            time.sleep(min(ms / 1000.0 / max(0.05, self.speed), 2.0))
        self._yield()

    def virtual_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000.0 * self.speed

    def _yield(self):
        """让出 CPU，顺便做配件 update（保证动画/传感器时序推进）"""
        self._iter_since += 1
        if self._iter_since % 4 == 0:
            for m in list(self.modules):
                try:
                    m.update(self, 4.0 * self.speed)
                except Exception:
                    pass
        time.sleep(0)

    def tone(self, pin, freq, dur=None):
        dev = self.device_on(pin, "buzzer")
        if dev:
            dev.tone(int(freq))
        else:
            pid = self._pin(pin)
            if pid:
                self._drive(pid, 1)

    def no_tone(self, pin=None):
        dev = self.device_on(pin, "buzzer") if pin is not None else None
        if dev:
            dev.no_tone()
        elif pin is not None:
            pid = self._pin(pin)
            if pid:
                self._drive(pid, 0)

    # ------------------------------------------------------------------ 运行
    def start(self, code: str):
        self.stop()
        for m in self.modules:
            m.rt = self
        self.rebuild_nets()
        self.serial_in.clear()
        self.code = code
        try:
            py_src, line_map, warns, includes = xlate.translate(code)
        except xlate.XlateError as e:
            raise RuntimeError(str(e)) from None
        self._py_source = py_src
        self._line_map = line_map
        self.ns = self._namespace()
        for w in warns:
            self.serial_out.put("[提示] " + w)

        # 先在当前线程编译一次，语法错误立刻报出来
        try:
            compile(py_src, "<sketch>", "exec")
        except SyntaxError as e:
            line = self._map_line(e.lineno or 0)
            raise RuntimeError("语法错误（第 %d 行附近）：%s" % (line, e.msg)) from None

        self._stop.clear()
        self.running = True
        self.started_at = time.perf_counter()
        self.thread = threading.Thread(target=self._run_loop, name="sketch", daemon=True)
        self.thread.start()

    def _map_line(self, py_line: int) -> int:
        if 0 < py_line <= len(self._line_map) and self._line_map[py_line - 1]:
            return self._line_map[py_line - 1]
        return py_line

    def _run_loop(self):
        ns = self.ns
        try:
            exec(compile(self._py_source, "<sketch>", "exec"), ns)
            setup = ns.get("setup")
            loop = ns.get("loop")
            if callable(setup):
                setup()
            if not callable(loop):
                self.serial_out.put("[提示] 没有 loop()，仿真停在 setup() 之后")
                self.running = False
                return
            while not self._stop.is_set():
                loop()
                self._iter_since += 1
                if self._iter_since % 16 == 0:
                    for m in list(self.modules):
                        try:
                            m.update(self, 16.0 * self.speed)
                        except Exception:
                            pass
                time.sleep(0)     # 让出 GIL，界面不卡
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)
            line = 0
            for fr in reversed(tb):
                if fr.filename == "<sketch>":
                    line = self._map_line(fr.lineno)
                    break
            self.serial_out.put("[错误] 第 %d 行：%s" % (line, e))
        finally:
            self.running = False

    def stop(self):
        self._stop.set()
        self.running = False
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=0.6)
        self.thread = None

    # ------------------------------------------------------------------ 外部输入
    def write_serial(self, text: str):
        for ch in text + "\n":
            self.serial_in.append(ch)
        self.serial_out.put(">> " + text)

    def drain_serial(self, limit=200):
        out = []
        while len(out) < limit:
            try:
                out.append(self.serial_out.get_nowait())
            except queue.Empty:
                break
        return out


# --------------------------------------------------------------------------- 杂项
class _EEPROM:
    def __init__(self):
        self.d = {}

    def read(self, a):
        return self.d.get(int(a), 0)

    def write(self, a, v):
        self.d[int(a)] = int(v)

    def update(self, a, v):
        self.write(a, v)

    def begin(self, *a):
        pass

    def commit(self, *a):
        pass

    def length(self):
        return 1024


class _Wire:
    def begin(self, *a):
        pass

    def beginTransmission(self, *a):
        pass

    def endTransmission(self, *a):
        return 0

    def write(self, *a):
        pass

    def requestFrom(self, *a):
        return 0

    def read(self):
        return 0

    def available(self):
        return 0

    def setClock(self, *a):
        pass


class _SPI:
    def begin(self, *a):
        pass

    def transfer(self, b):
        return b

    def end(self, *a):
        pass


class _Stub:
    """没仿真实现的库：调用不崩，只提示一次"""

    def __init__(self, name, rt):
        self._name = name
        self._rt = rt
        self._warned = False

    def __getattr__(self, item):
        def _noop(*a, **k):
            if not self._warned:
                self._warned = True
                self._rt.serial_out.put("[%s] 这个库还没仿真实现，调用被忽略（不影响接线）" % self._name)
            return 0
        return _noop


def random_range(a=2147483647, b=None):
    import random as _r
    if b is None:
        return _r.randint(0, max(0, int(a) - 1))
    return _r.randint(int(a), int(b) - 1)


def sprintf(buf, fmt, *args):
    out = str(fmt)
    vals = list(args)
    for token in ("%d", "%i", "%u", "%s", "%f", "%x", "%c", "%ld", "%lu"):
        while token in out and vals:
            v = vals.pop(0)
            if token in ("%s",):
                rep = str(v)
            elif token in ("%x",):
                rep = format(int(v), "x")
            elif token in ("%c",):
                rep = chr(int(v))
            elif token in ("%f",):
                rep = "%.2f" % float(v)
            else:
                rep = fmt_num(v)
            out = out.replace(token, rep, 1)
    if isinstance(buf, Buf):
        for i, ch in enumerate(out[: len(buf) - 1]):
            buf[i] = ord(ch)
        buf[min(len(out), len(buf) - 1)] = 0
    return len(out)

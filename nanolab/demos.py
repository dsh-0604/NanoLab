# -*- coding: utf-8 -*-
"""演示场景：一键摆好板子/配件/接线并运行代码（也用来验证仿真）"""

from __future__ import annotations

BLINK = """#include <Arduino.h>
void setup() { Serial.begin(115200); pinMode(8, OUTPUT); Serial.println("C3 板载 LED 开始闪烁"); }
void loop() {
  digitalWrite(8, LOW);
  delay(500);
  digitalWrite(8, HIGH);
  delay(500);
}
"""

DHT = """#include <DHT.h>
#define DHTPIN 4
DHT dht(DHTPIN, DHT22);
void setup() { Serial.begin(115200); dht.begin(); }
void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  Serial.print("温度: "); Serial.print(t);
  Serial.print(" C   湿度: "); Serial.print(h); Serial.println(" %");
  delay(1500);
}
"""

OLED = """#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

Adafruit_SSD1306 display(128, 64, &Wire, -1);
DHT dht(6, DHT22);

void setup() {
  Serial.begin(115200);
  dht.begin();
  Wire.begin();
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.setTextColor(WHITE);
}
void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("NanoCode Lab");
  display.setTextSize(2);
  display.setCursor(0, 20);
  display.print(t); display.println(" C");
  display.setCursor(0, 44);
  display.print(h); display.println(" %");
  display.display();
  delay(1000);
}
"""

BUTTON = """#include <Arduino.h>
const int BTN = 2;
const int LED = 13;
void setup() { Serial.begin(115200); pinMode(BTN, INPUT); pinMode(LED, OUTPUT); }
void loop() {
  if (digitalRead(BTN) == HIGH) { digitalWrite(LED, HIGH); Serial.println("按下 → 灯亮"); }
  else { digitalWrite(LED, LOW); }
  delay(120);
}
"""

SERVO = """#include <Servo.h>
Servo myservo;
int angle = 0;
int step = 5;
void setup() { Serial.begin(115200); myservo.attach(9); }
void loop() {
  myservo.write(angle);
  angle = angle + step;
  if (angle >= 180) { step = -5; }
  if (angle <= 0) { step = 5; }
  Serial.print("角度: "); Serial.println(angle);
  delay(40);
}
"""

ULTRASONIC = """#include <Arduino.h>
const int TRIG = 7;
const int ECHO = 8;
void setup() { Serial.begin(115200); pinMode(TRIG, OUTPUT); pinMode(ECHO, INPUT); }
void loop() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  long dur = pulseIn(ECHO, HIGH, 30000);
  long dist = dur / 58;
  Serial.print("距离: "); Serial.print(dist); Serial.println(" cm");
  delay(600);
}
"""

NEOPIXEL = """#include <Adafruit_NeoPixel.h>
Adafruit_NeoPixel ring(8, 4, NEO_GRB + NEO_KHZ800);
void setup() { Serial.begin(115200); ring.begin(); ring.setBrightness(120); ring.show(); }
void loop() {
  for (int i = 0; i < 8; i++) {
    ring.clear();
    ring.setPixelColor(i, ring.Color(0, 180, 255));
    ring.show();
    delay(120);
  }
  delay(200);
}
"""


RESISTOR_LED = """#include <Arduino.h>
const int LED_PIN = 4;
void setup() { Serial.begin(115200); pinMode(LED_PIN, OUTPUT); Serial.println("电阻限流点灯：调右边的阻值试试"); }
void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(600);
  digitalWrite(LED_PIN, LOW);
  delay(600);
}
"""

def setup_demo(win, idx: int):
    canvas = win.canvas
    demo = idx - 1

    def board(bid):
        win.board_id = bid
        i = win.board_combo.findData(bid)
        if i >= 0:
            win.board_combo.blockSignals(True)
            win.board_combo.setCurrentIndex(i)
            win.board_combo.blockSignals(False)
        canvas.set_board(bid)

    def add(geo_id, x, y):
        return canvas.add_module(geo_id, _pos(x, y))

    if demo == 0:
        board("esp32-c3-devkitm-1")
        win.run_code(BLINK, "blink.cpp")

    elif demo == 1:
        board("esp32-c3-devkitm-1")
        dht = add("dht22", 420, 80)
        canvas.connect("GPIO4", dht._uid, "DATA")
        canvas.connect("3V3", dht._uid, "VCC")
        canvas.connect("GND1", dht._uid, "GND")
        win.run_code(DHT, "dht.cpp")

    elif demo == 2:
        board("esp32-c3-devkitm-1")
        oled = add("ssd1306-oled", 380, 70)
        dht = add("dht22", 380, 300)
        canvas.connect("GPIO4", oled._uid, "SDA")
        canvas.connect("GPIO5", oled._uid, "SCL")
        canvas.connect("3V3", oled._uid, "VCC")
        canvas.connect("GND1", oled._uid, "GND")
        canvas.connect("GPIO6", dht._uid, "DATA")
        canvas.connect("3V3", dht._uid, "VCC")
        canvas.connect("GND1", dht._uid, "GND")
        win.run_code(OLED, "oled.cpp")

    elif demo == 3:
        board("arduino-uno-r3")
        btn = add("button-module", 520, 80)
        led = add("led", 560, 260)
        canvas.connect("D2", btn._uid, "OUT")
        canvas.connect("5V", btn._uid, "VCC")
        canvas.connect("GND1", btn._uid, "GND")
        canvas.connect("D13", led._uid, "A")
        canvas.connect("GND2", led._uid, "K")
        win.run_code(BUTTON, "button.cpp")

    elif demo == 4:
        board("arduino-uno-r3")
        sv = add("servo-sg90", 520, 90)
        canvas.connect("D9", sv._uid, "SIG")
        canvas.connect("5V", sv._uid, "VCC")
        canvas.connect("GND1", sv._uid, "GND")
        win.run_code(SERVO, "servo.cpp")

    elif demo == 5:
        board("arduino-uno-r3")
        us = add("hc-sr04", 500, 90)
        canvas.connect("D7", us._uid, "TRIG")
        canvas.connect("D8", us._uid, "ECHO")
        canvas.connect("5V", us._uid, "VCC")
        canvas.connect("GND1", us._uid, "GND")
        win.run_code(ULTRASONIC, "sonar.cpp")

    elif demo == 6:
        board("esp32-c3-devkitm-1")
        ring = add("ws2812-ring", 430, 90)
        canvas.connect("GPIO4", ring._uid, "DIN")
        canvas.connect("5V", ring._uid, "5V")
        canvas.connect("GND1", ring._uid, "GND")
        win.run_code(NEOPIXEL, "ring.cpp")

    elif demo == 7:
        # 电阻限流：GPIO4 → 电阻 → LED → GND（正确接法，灯亮不烧）
        board("esp32-c3-devkitm-1")
        r = add("resistor", 400, 120)
        led = add("led", 300, 260)
        r.behavior.props["ohms"] = 220
        r.behavior.state["ohms"] = 220
        canvas.connect_eps(("b", "GPIO4"), ("m", r._uid, "1"))
        canvas.connect_eps(("m", r._uid, "2"), ("m", led._uid, "A"))
        canvas.connect_eps(("m", led._uid, "K"), ("b", "GND1"))
        win.run_code(RESISTOR_LED, "resistor.cpp")

    elif demo == 8:
        # 不加电阻直接接 LED：电流过大 → 烧毁（概率 100% 时必烧）
        board("esp32-c3-devkitm-1")
        led = add("led", 320, 240)
        canvas.connect_eps(("b", "GPIO4"), ("m", led._uid, "A"))
        canvas.connect_eps(("m", led._uid, "K"), ("b", "GND1"))
        win.run_code(RESISTOR_LED, "burn.cpp")

    win.canvas.fit()


def _pos(x_mm: float, y_mm: float):
    from PySide6.QtCore import QPointF
    return QPointF(x_mm, y_mm)

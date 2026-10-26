# -*- coding: utf-8 -*-
"""
xlate.py —— Arduino C++ 子集 → Python 源码翻译器

为什么这么做：NanoCode 里写的是真实 Arduino C++，实验室只要把它翻译成 Python
在本地进程里跑起来，就是一个纯原生程序，不涉及任何网页技术。

支持：
  类型    int float double char bool byte short long unsigned const static
          String uint8_t..uint64_t size_t word
  声明    int x = 1;  float y;  int a[3] = {1,2,3};  char buf[32];
          DHT dht(4, DHT22);   Servo s;   Adafruit_SSD1306 oled(128, 64, &Wire, -1);
  函数    void setup() {}  void loop() {}  int add(int a, int b) {}
  控制    if/else  for  while  do-while  break  continue  return
  运算    + - * / % 比较  && || !  位运算  复合赋值  i++ / i-- （语句与 for 步进）
  预处理  #include（只记录）  #define 对象宏  #if 0 块

不支持（给中文报错，绝不静默出错）：class/struct/typedef/enum/模板/switch/三目/指针运算
"""

from __future__ import annotations

PRIMITIVE = {
    "int", "float", "double", "char", "bool", "byte", "boolean", "short", "long",
    "unsigned", "signed", "void", "size_t", "word",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "String", "const", "static", "volatile", "register", "auto",
}
QUAL = {"const", "static", "volatile", "register", "auto", "unsigned", "signed", "short", "long"}
KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "default", "break", "continue",
    "return", "true", "false", "NULL", "nullptr", "goto", "new", "delete", "this",
}
UNSUPPORTED = {
    "class": "class（类）", "struct": "struct（结构体）", "typedef": "typedef",
    "enum": "enum（枚举）", "template": "template（模板）", "namespace": "namespace",
    "union": "union", "operator": "operator 重载", "virtual": "virtual",
}
MULTI = ["<<=", ">>=", "...", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
         "==", "!=", "<=", ">=", "&&", "||", "<<", ">>", "->", "::", "##"]


class XlateError(Exception):
    def __init__(self, msg: str, line: int = 0):
        super().__init__(msg)
        self.line = line


# --------------------------------------------------------------------------- 预处理
def strip_comments(src: str) -> str:
    out = []
    i, n, quote = 0, len(src), None
    while i < n:
        c = src[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                if src[i] == "\n":
                    out.append("\n")
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def read_directives(src: str):
    """返回 (去掉指令的源码, 宏字典, include 列表)"""
    lines = src.split("\n")
    defs: dict[str, str] = {}
    includes: list[str] = []
    out: list[str] = []
    skip = 0
    for line in lines:
        t = line.strip()
        if not t.startswith("#"):
            out.append("" if skip else line)
            continue
        body = t[1:].strip()
        m = body.split(None, 1)
        head = m[0] if m else ""
        rest = m[1].strip() if len(m) > 1 else ""
        if head == "include":
            inc = rest.replace("<", "").replace(">", "").replace('"', "").strip()
            if inc:
                includes.append(inc)
        elif head == "define":
            parts = rest.split(None, 1)
            if len(parts) == 2:
                defs[parts[0]] = parts[1].strip()
            elif parts:
                defs[parts[0]] = "1"
        elif head == "if" and rest.startswith("0"):
            skip = 1
        elif head in ("if", "ifdef", "ifndef") and skip:
            skip += 1
        elif head == "endif" and skip:
            skip -= 1
        out.append("")
    return "\n".join(out), defs, includes


# --------------------------------------------------------------------------- 词法
def tokenize(src: str):
    toks = []
    i, n, line, col = 0, len(src), 1, 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            col = 1
            i += 1
            continue
        if c in " \t\r":
            col += 1
            i += 1
            continue
        sc = col
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j, buf = i, ""
            if c == "0" and i + 1 < n and src[i + 1] in "xXbB":
                buf = c + src[i + 1]
                j = i + 2
                while j < n and (src[j].isalnum() or src[j] == "_"):
                    buf += src[j]
                    j += 1
            else:
                while j < n and (src[j].isdigit() or src[j] in "._"):
                    buf += src[j]
                    j += 1
            while j < n and src[j] in "uUlLfF":
                j += 1
            toks.append(("num", buf.replace("_", ""), line, sc))
            col += j - i
            i = j
            continue
        if c in "\"'":
            k, buf = i + 1, c
            while k < n:
                ch = src[k]
                if ch == "\\" and k + 1 < n:
                    buf += ch + src[k + 1]
                    k += 2
                    continue
                buf += ch
                k += 1
                if ch == c:
                    break
            toks.append(("str", buf, line, sc))
            col += k - i
            i = k
            continue
        if c.isalpha() or c == "_":
            j, buf = i, ""
            while j < n and (src[j].isalnum() or src[j] == "_"):
                buf += src[j]
                j += 1
            toks.append(("id", buf, line, sc))
            col += j - i
            i = j
            continue
        hit = None
        for m in MULTI:
            if src.startswith(m, i):
                hit = m
                break
        if hit:
            toks.append(("op", hit, line, sc))
            col += len(hit)
            i += len(hit)
            continue
        kind = "op" if c in "+-*/%<>=!&|^~?:" else "punct"
        toks.append((kind, c, line, sc))
        col += 1
        i += 1
    return toks


def expand_macros(toks, defs):
    if not defs:
        return toks
    out = []
    for idx, tk in enumerate(toks):
        kind, val, ln, cl = tk
        if kind == "id" and val in defs and not (idx + 1 < len(toks) and toks[idx + 1][1] == "("):
            sub = tokenize(defs[val])
            if not sub:
                sub = [("num", "1", ln, cl)]
            out.extend((k, v, ln, c) for k, v, _, c in sub)
        else:
            out.append(tk)
    return out


# --------------------------------------------------------------------------- 工具
def is_type(tk):
    return tk is not None and tk[0] == "id" and tk[1] in PRIMITIVE


def is_p(tk, v):
    return tk is not None and tk[0] == "punct" and tk[1] == v


def is_o(tk, v):
    return tk is not None and tk[0] == "op" and tk[1] == v


def is_class_like(name: str) -> bool:
    return bool(name) and name[0].isupper() and name != "String"



def collect_globals(toks):
    """扫描顶层（大括号深度 0）的变量声明，收集名字。
    Arduino 代码里 loop() 直接改全局变量是常态，Python 里必须显式 global。"""
    names = []
    depth = 0
    i, n = 0, len(toks)
    while i < n:
        kind, val, ln, cl = toks[i]
        if kind == "punct" and val == "{":
            depth += 1
            i += 1
            continue
        if kind == "punct" and val == "}":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0 and (is_type(toks[i]) or _looks_like_class_type(toks, i)):
            j = i
            if is_type(toks[i]):
                while j < n and is_type(toks[j]):
                    j += 1
            else:
                j = i + 1
            while j < n and (is_o(toks[j], "*") or is_o(toks[j], "&")):
                j += 1
            # 函数定义？那就不是变量
            is_func = (j < n and toks[j][0] == "id" and j + 1 < n and is_p(toks[j + 1], "("))
            if not is_func:
                k = j
                while k < n:
                    if toks[k][0] == "id":
                        names.append(toks[k][1])
                        k += 1
                        # 跳过数组维度 / 初始化
                        while k < n and not (is_p(toks[k], ";") or is_p(toks[k], ",")):
                            if is_p(toks[k], "{"):
                                d = 0
                                while k < n:
                                    if is_p(toks[k], "{"):
                                        d += 1
                                    elif is_p(toks[k], "}"):
                                        d -= 1
                                        if d == 0:
                                            k += 1
                                            break
                                    k += 1
                                continue
                            k += 1
                        if k < n and is_p(toks[k], ","):
                            k += 1
                            continue
                        break
                    k += 1
                i = k if k > i else i + 1
                continue
        i += 1
    return names


def _looks_like_class_type(toks, i):
    tk = toks[i]
    if tk[0] != "id" or tk[1] in PRIMITIVE or tk[1] in KEYWORDS or tk[1] in UNSUPPORTED:
        return False
    if not is_class_like(tk[1]):
        return False
    nx = toks[i + 1] if i + 1 < len(toks) else None
    return nx is not None and (nx[0] == "id" or is_o(nx, "*") or is_o(nx, "&"))


class Emitter:
    def __init__(self):
        self.lines: list[str] = []
        self.line_map: list[int] = []
        self.indent = 0

    def add(self, text: str, src_line: int = 0, delta: int = 0):
        self.indent = max(0, self.indent + delta)
        self.lines.append(("    " * self.indent) + text)
        self.line_map.append(src_line)

    def source(self) -> str:
        return "\n".join(self.lines) + "\n"


# --------------------------------------------------------------------------- 编译
class Compiler:
    def __init__(self, toks, board_pins=None, globals_=None):
        self.t = toks
        self.globals_ = globals_ or []
        self.n = len(toks)
        self.em = Emitter()
        self.board_pins = board_pins or {}
        self.warnings: list[str] = []

    # ---------------- 表达式 ----------------
    def expr(self, a: int, b: int) -> str:
        """把 [a, b) 的 token 变成 Python 表达式文本"""
        out: list[str] = []
        i = a
        while i < b:
            kind, val, ln, cl = self.t[i]
            # C 风格强转 (int) x
            if is_p(self.t[i], "("):
                j = i + 1
                while j < b and (is_type(self.t[j]) or is_o(self.t[j], "*") or is_o(self.t[j], "&")):
                    j += 1
                all_type = j > i + 1 and is_p(self.t[j], ")") and all(
                    is_type(self.t[k]) or is_o(self.t[k], "*") or is_o(self.t[k], "&") for k in range(i + 1, j)
                )
                if all_type:
                    nx = self.t[j + 1] if j + 1 < b else None
                    starts_value = nx is not None and (
                        (nx[0] == "id" and nx[1] not in KEYWORDS and nx[1] not in PRIMITIVE)
                        or nx[0] in ("num", "str")
                        or (nx[0] in ("punct", "op") and nx[1] in ("(", "-", "!", "~"))
                    )
                    if starts_value:
                        i = j + 1
                        continue
            if kind == "op" and val in ("&&", "||"):
                out.append("and" if val == "&&" else "or")
                i += 1
                continue
            if kind == "op" and val == "!":
                out.append("not")
                i += 1
                continue
            if kind == "op" and val == "->":
                out.append(".")
                i += 1
                continue
            if kind == "op" and val == "::":
                i += 1
                continue
            if kind == "op" and val in ("&",) and (
                i == a or is_p(self.t[i - 1], "(") or is_p(self.t[i - 1], ",") or is_o(self.t[i - 1], "=")
            ):
                i += 1   # &obj 引用传参 → 去掉
                continue
            if kind == "op" and val in ("++", "--"):
                raise XlateError("第 %d 行：++/-- 只能单独成句或写在 for 的步进里（写成 i++; 或 i += 1;）" % ln, ln)
            if kind == "id" and val in ("true", "false", "NULL", "nullptr"):
                out.append({"TRUE": "True", "FALSE": "False", "NULL": "None", "nullptr": "None"}[val.upper()] if val.upper() in ("TRUE", "FALSE", "NULL", "NULLPTR") else "None")
                i += 1
                continue
            if kind == "id" and val == "sizeof":
                out.append("__sizeof")
                i += 1
                continue
            if kind == "id" and val == "String":
                out.append("String")
                i += 1
                continue
            out.append(val)
            i += 1
        return join_tokens(out)

    # ---------------- 语句 ----------------
    def block(self, i: int, stop_brace: bool = True) -> int:
        while i < self.n:
            tk = self.t[i]
            if stop_brace and is_p(tk, "}"):
                return i
            if is_p(tk, "}"):
                i += 1
                continue
            i = self.statement(i)
        return i

    def statement(self, i: int) -> int:
        tk = self.t[i]
        if tk is None:
            return i
        if is_p(tk, ";"):
            return i + 1
        if is_p(tk, "{"):
            i += 1
            i = self.block(i, True)
            return i + 1 if i < self.n and is_p(self.t[i], "}") else i

        if tk[0] == "id" and tk[1] in UNSUPPORTED:
            raise XlateError(
                "第 %d 行用了 %s。实验室只支持 Arduino 新手写法（函数/变量/if/for/while），"
                "把结构体或类拆成几个普通变量试试。" % (tk[2], UNSUPPORTED[tk[1]]), tk[2])

        # if / else
        if tk[0] == "id" and tk[1] == "if":
            close = self._paren(i + 1)
            cond = self.expr(i + 2, close)
            self.em.add("if %s:" % cond, tk[2])
            i = self._py_body(close + 1, indent=True)
            if i < self.n and self.t[i][0] == "id" and self.t[i][1] == "else":
                nxt = self.t[i + 1] if i + 1 < self.n else None
                if nxt and nxt[0] == "id" and nxt[1] == "if":
                    sub = Compiler.__new__(Compiler)
                    sub.__dict__.update(self.__dict__)
                    sub.em = Emitter()
                    sub.statement(i + 1)
                    first = sub.em.lines[0].strip()
                    self.em.add("el" + first, self.t[i][2])
                    self.em.indent += 1
                    for k in range(1, len(sub.em.lines)):
                        self.em.lines.append(sub.em.lines[k])
                        self.em.line_map.append(sub.em.line_map[k])
                    self.em.indent -= 1
                    return sub._last_i
                self.em.add("else:", self.t[i][2])
                i = self._py_body(i + 1, indent=True)
            return i

        # for
        if tk[0] == "id" and tk[1] == "for":
            close = self._paren(i + 1)
            segs = self._split_semis(i + 2, close)
            init, cond, step = segs
            self.em.add("# for", tk[2])
            if init[0] < init[1]:
                self._decl_or_expr(init[0], init[1], indent_now=False)
            step_text = ""
            if step[0] < step[1]:
                step_text = self._step_text(step[0], step[1])
            cond_text = self.expr(cond[0], cond[1]) if cond[0] < cond[1] else "True"
            self.em.add("while %s:" % cond_text, tk[2])
            self._body_with_continue(close + 1, step_text)
            return self._last_i

        # while
        if tk[0] == "id" and tk[1] == "while":
            close = self._paren(i + 1)
            cond = self.expr(i + 2, close)
            self.em.add("while %s:" % cond, tk[2])
            self._body_with_continue(close + 1, "")
            return self._last_i

        # do { } while (...)
        if tk[0] == "id" and tk[1] == "do":
            self.em.add("while True:", tk[2])
            self._body_plain(i + 1)
            j = self._last_i
            if j < self.n and self.t[j][0] == "id" and self.t[j][1] == "while":
                close = self._paren(j + 1)
                cond = self.expr(j + 2, close)
                self.em.add("if not (%s):" % cond, self.t[j][2])
                self.em.add("break", self.t[j][2], +1)
                j = close + 1
                if j < self.n and is_p(self.t[j], ";"):
                    j += 1
            return j

        # return / break / continue
        if tk[0] == "id" and tk[1] in ("return", "break", "continue"):
            end = self._expr_end(i + 1, {";"})
            inner = self.expr(i + 1, end) if end > i + 1 else ""
            self.em.add(tk[1] + ((" " + inner) if inner else ""), tk[2])
            return end + 1 if end < self.n and is_p(self.t[end], ";") else end

        # switch 不支持
        if tk[0] == "id" and tk[1] == "switch":
            raise XlateError("第 %d 行用了 switch。实验室暂不支持，改成 if / else if 就行。" % tk[2], tk[2])

        # 声明
        if is_type(tk) or self._is_class_decl(i):
            return self._decl(i)

        # 自增自减语句
        if tk[0] == "id" and i + 1 < self.n and is_o(self.t[i + 1], "++"):
            self.em.add("%s += 1" % tk[1], tk[2])
            return i + 3 if i + 2 < self.n and is_p(self.t[i + 2], ";") else i + 2
        if tk[0] == "id" and i + 1 < self.n and is_o(self.t[i + 1], "--"):
            self.em.add("%s -= 1" % tk[1], tk[2])
            return i + 3 if i + 2 < self.n and is_p(self.t[i + 2], ";") else i + 2

        # 表达式语句
        end = self._expr_end(i, {";"})
        text = self.expr(i, end)
        if text.strip():
            self.em.add(text, tk[2])
        return end + 1 if end < self.n and is_p(self.t[end], ";") else end

    # ---------------- 内部工具 ----------------
    _last_i = 0

    def _paren(self, i):
        depth = 0
        for j in range(i, self.n):
            if is_p(self.t[j], "("):
                depth += 1
            elif is_p(self.t[j], ")"):
                depth -= 1
                if depth == 0:
                    return j
        return self.n - 1

    def _brace(self, i):
        depth = 0
        for j in range(i, self.n):
            if is_p(self.t[j], "{"):
                depth += 1
            elif is_p(self.t[j], "}"):
                depth -= 1
                if depth == 0:
                    return j
        return self.n - 1

    def _expr_end(self, i, stops):
        depth = 0
        for j in range(i, self.n):
            k, v, _, _ = self.t[j]
            if k == "punct":
                if v in "([{":
                    depth += 1
                elif v in ")]}":
                    if depth == 0:
                        return j
                    depth -= 1
                elif depth == 0 and v in stops:
                    return j
            elif depth == 0 and k == "op" and v in stops:
                return j
        return self.n

    def _split_semis(self, a, b):
        segs, start, depth = [], a, 0
        for j in range(a, b):
            v = self.t[j][1]
            if v in "([{":
                depth += 1
            elif v in ")]}":
                depth -= 1
            elif depth == 0 and v == ";":
                segs.append((start, j))
                start = j + 1
        segs.append((start, b))
        while len(segs) < 3:
            segs.append((b, b))
        return segs[:3]

    def _is_class_decl(self, i):
        tk = self.t[i]
        if tk[0] != "id" or tk[1] in PRIMITIVE or tk[1] in KEYWORDS or tk[1] in UNSUPPORTED:
            return False
        if not is_class_like(tk[1]):
            return False
        nx = self.t[i + 1] if i + 1 < self.n else None
        return nx is not None and (nx[0] == "id" or is_o(nx, "*") or is_o(nx, "&"))

    # 语句体（块或单语句），用于 if/else
    def _py_body(self, i, indent=True):
        if is_p(self.t[i], "{"):
            self.em.indent += 1
            j = self.block(i + 1, True)
            self.em.indent -= 1
            self._last_i = j + 1
            return j + 1
        self.em.indent += 1
        j = self.statement(i)
        self.em.indent -= 1
        self._last_i = j
        return j

    def _body_plain(self, i):
        self.em.indent += 1
        if is_p(self.t[i], "{"):
            j = self.block(i + 1, True)
            j = j + 1
        else:
            j = self.statement(i)
        self.em.indent -= 1
        self._last_i = j
        return j

    def _body_with_continue(self, i, step_text):
        self.em.indent += 1
        if is_p(self.t[i], "{"):
            j = self.block(i + 1, True) + 1
        else:
            j = self.statement(i)
        if step_text:
            self.em.add(step_text, 0)
        self.em.indent -= 1
        self._last_i = j
        return j

    def _step_text(self, a, b):
        # i++ / i-- / i += 1
        if b - a == 2 and self.t[a][0] == "id" and self.t[a + 1][1] in ("++", "--"):
            return "%s %s 1" % (self.t[a][1], "+=" if self.t[a + 1][1] == "++" else "-=")
        return self.expr(a, b)

    def _decl_or_expr(self, a, b, indent_now=False):
        if a >= b:
            return
        if is_type(self.t[a]) or self._is_class_decl(a):
            self._decl(a)
        else:
            self.em.add(self.expr(a, b), self.t[a][2])

    # 声明：TYPE [*&] name [ (args) | [dim] | = init ] [, ...]
    def _decl(self, i):
        ref_line = self.t[i][2]
        type_name = None
        j = i
        if self._is_class_decl(i):
            type_name = self.t[i][1]
            j = i + 1
        else:
            while j < self.n and is_type(self.t[j]):
                if self.t[j][1] not in QUAL:
                    type_name = self.t[j][1]
                j += 1
        while j < self.n and (is_o(self.t[j], "*") or is_o(self.t[j], "&")):
            j += 1

        # 函数定义 / 原型
        if j < self.n and self.t[j][0] == "id" and j + 1 < self.n and is_p(self.t[j + 1], "("):
            close = self._paren(j + 1)
            after = self.t[close + 1] if close + 1 < self.n else None
            if after is not None and is_p(after, "{"):
                params = []
                for k in range(j + 2, close):
                    tk = self.t[k]
                    if is_type(tk) or is_o(tk, "*") or is_o(tk, "&"):
                        continue
                    if is_p(tk, ","):
                        continue
                    params.append(tk[1])
                self.em.add("def %s(%s):" % (self.t[j][1], ", ".join(params)), ref_line)
                self.em.indent += 1
                gs = [g for g in self.globals_ if g not in params]
                if gs:
                    self.em.add("global " + ", ".join(gs), ref_line)
                k = self.block(close + 2, True)
                if not any(l.strip() for l in self.em.lines[-1:]):
                    pass
                self.em.add("pass", ref_line)   # 空函数体兜底
                self.em.indent -= 1
                k = k + 1
                # 去掉多余的 pass：如果函数体非空，pass 会多余但无害
                return k
            if after is not None and is_p(after, ";"):
                if is_class_like(type_name or ""):
                    # DHT dht(4, DHT22);
                    name = self.t[j][1]
                    args = self.expr(j + 2, close) if close > j + 2 else ""
                    self.em.add("%s = %s(%s)" % (name, type_name, args), ref_line)
                    return close + 2
                return close + 2     # 纯函数原型，丢掉

        # 变量声明
        cur = j
        while cur < self.n:
            tk = self.t[cur]
            if tk[0] != "id":
                break
            name = tk[1]
            cur += 1
            if is_p(self.t[cur], "("):          # 对象声明
                close = self._paren(cur)
                args = self.expr(cur + 1, close) if close > cur + 1 else ""
                self.em.add("%s = %s(%s)" % (name, type_name or "object", args), ref_line)
                cur = close + 1
                if cur < self.n and is_p(self.t[cur], ";"):
                    cur += 1
                return cur
            if is_p(self.t[cur], "["):          # 数组
                depth, j2, dim = 1, cur + 1, ""
                while j2 < self.n:
                    v = self.t[j2][1]
                    if v == "[":
                        depth += 1
                    elif v == "]":
                        depth -= 1
                        if depth == 0:
                            break
                    dim += v
                    j2 += 1
                cur = j2 + 1
                if cur < self.n and is_o(self.t[cur], "="):
                    cur += 1
                    if is_p(self.t[cur], "{"):
                        close = self._brace(cur)
                        vals = self.expr(cur + 1, close)
                        self.em.add("%s = [%s]" % (name, vals), ref_line)
                        cur = close + 1
                    else:
                        end = self._expr_end(cur, {";", ","})
                        self.em.add("%s = %s" % (name, self.expr(cur, end)), ref_line)
                        cur = end
                else:
                    maker = "__mk_buf" if type_name == "char" else "__mk_arr"
                    self.em.add("%s = %s(%s)" % (name, maker, dim or "1"), ref_line)
            elif cur < self.n and is_o(self.t[cur], "="):
                end = self._expr_end(cur + 1, {";", ","})
                self.em.add("%s = %s" % (name, self.expr(cur + 1, end)), ref_line)
                cur = end
            elif type_name == "String":
                self.em.add('%s = ""' % name, ref_line)
            elif is_class_like(type_name or ""):
                self.em.add("%s = %s()" % (name, type_name), ref_line)
            elif type_name in ("char",):
                self.em.add("%s = 0" % name, ref_line)
            elif type_name in ("float", "double"):
                self.em.add("%s = 0.0" % name, ref_line)
            elif type_name == "bool":
                self.em.add("%s = False" % name, ref_line)
            else:
                self.em.add("%s = 0" % name, ref_line)

            if cur < self.n and is_p(self.t[cur], ","):
                cur += 1
                while cur < self.n and (is_o(self.t[cur], "*") or is_o(self.t[cur], "&")):
                    cur += 1
                continue
            break
        if cur < self.n and is_p(self.t[cur], ";"):
            cur += 1
        return cur


def join_tokens(parts: list[str]) -> str:
    """把 token 拼成 Python 文本，空格按需要插入"""
    no_space_before = {")", "]", ",", ";", ".", ":", "("}  # "(" 前面由后续规则处理
    out = ""
    prev = ""
    for p in parts:
        if p == "":
            continue
        need = True
        if not out:
            need = False
        elif p in (")", "]", ",", ":", ".", ";"):
            need = False
        elif prev in ("(", "[", "."):
            need = False
        elif p == "(" and (prev.isidentifier() or prev == ")" or prev == "]"):
            need = False
        elif prev in ("not",) and p not in ("(", "["):
            need = True
        if need:
            out += " "
        out += p
        prev = p
    return out.strip()


def translate(src: str, board_pins: dict | None = None):
    """返回 (python 源码, 行号映射, 警告列表, include 列表)"""
    clean = strip_comments(src)
    clean, defs, includes = read_directives(clean)
    toks = expand_macros(tokenize(clean), defs)
    comp = Compiler(toks, board_pins, collect_globals(toks))
    i = 0
    while i < comp.n:
        i = comp.statement(i)
    if not any(("def setup" in l) or ("def loop" in l) for l in comp.em.lines):
        comp.warnings.append("没找到 setup() / loop()：代码不会自己动起来")
    return comp.em.source(), comp.em.line_map, comp.warnings, includes

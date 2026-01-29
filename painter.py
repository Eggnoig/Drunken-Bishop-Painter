#!/usr/bin/env python3

import os
import sys
import base64
import hashlib
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QSpinBox,
    QSplitter, QTextEdit, QVBoxLayout, QWidget
)

# ASCII-only density ramp; S/E are injected separately.
RAMP = " .o+=*BOX@%&#/^"

def clamp(v, lo, hi):
    # Keep v inside [lo, hi] without branching noise elsewhere.
    return lo if v < lo else hi if v > hi else v

def bytes_from_string(text: str, encoding: str) -> bytes:
    # Replace invalid characters instead of raising, keeps UI forgiving.
    return text.encode(encoding, errors="replace")

def derive_bytes(data: bytes, mode: str, hash_name: str, salt: bytes, iterations: int) -> bytes:
    if mode == "Raw bytes":
        if salt or iterations > 1:
            # Manual re-hash for "raw bytes + salt/iterations".
            h = hashlib.new(hash_name)
            h.update(salt)
            h.update(data)
            out = h.digest()
            for _ in range(max(0, iterations - 1)):
                h = hashlib.new(hash_name)
                h.update(salt)
                h.update(out)
                out = h.digest()
            return out
        return data

    # mode == "Hash"
    if iterations <= 1 and not salt:
        h = hashlib.new(hash_name)
        h.update(data)
        return h.digest()

    # PBKDF2 for deterministic "strengthening" if requested
    try:
        return hashlib.pbkdf2_hmac(hash_name, data, salt or b"\x00", iterations)
    except ValueError:
        # Fallback for hashes not accepted by pbkdf2_hmac in some builds
        h = hashlib.new(hash_name)
        h.update(salt)
        h.update(data)
        out = h.digest()
        for _ in range(max(0, iterations - 1)):
            h = hashlib.new(hash_name)
            h.update(salt)
            h.update(out)
            out = h.digest()
        return out

def build_grid(data: bytes, width: int, height: int):
    if width < 5 or height < 5:
        raise ValueError("Board must be at least 5x5.")

    # Start in the middle and walk based on 2-bit chunks.
    grid = [[0] * width for _ in range(height)]
    x = width // 2
    y = height // 2
    sx, sy = x, y

    def step(dir2: int):
        nonlocal x, y
        # 0 up-left, 1 up-right, 2 down-left, 3 down-right
        if dir2 == 0:
            x -= 1; y -= 1
        elif dir2 == 1:
            x += 1; y -= 1
        elif dir2 == 2:
            x -= 1; y += 1
        else:
            x += 1; y += 1

        # Clamp to keep the bishop on the board.
        x = clamp(x, 0, width - 1)
        y = clamp(y, 0, height - 1)
        grid[y][x] += 1

    for b in data:
        for shift in (0, 2, 4, 6):
            step((b >> shift) & 0b11)

    ex, ey = x, y
    return grid, (sx, sy), (ex, ey)

def walk_positions(data: bytes, width: int, height: int):
    if width < 5 or height < 5:
        raise ValueError("Board must be at least 5x5.")

    x = width // 2
    y = height // 2
    sx, sy = x, y

    def step(dir2: int):
        nonlocal x, y
        if dir2 == 0:
            x -= 1; y -= 1
        elif dir2 == 1:
            x += 1; y -= 1
        elif dir2 == 2:
            x -= 1; y += 1
        else:
            x += 1; y += 1
        x = clamp(x, 0, width - 1)
        y = clamp(y, 0, height - 1)
        return x, y

    for b in data:
        for shift in (0, 2, 4, 6):
            yield step((b >> shift) & 0b11)

    return (sx, sy), (x, y)

def count_to_char(count: int) -> str:
    # Map visit count into the density ramp.
    return RAMP[min(count, len(RAMP) - 1)]

def ascii_box_lines(grid, start_pos, end_pos):
    h = len(grid)
    w = len(grid[0]) if h else 0
    sx, sy = start_pos
    ex, ey = end_pos

    top = "+" + "-" * w + "+"
    lines = [top]
    for y in range(h):
        row = []
        for x in range(w):
            # S/E override the density ramp.
            if (x, y) == (sx, sy):
                ch = "S"
            elif (x, y) == (ex, ey):
                ch = "E"
            else:
                ch = count_to_char(grid[y][x])
            row.append(ch)
        lines.append("|" + "".join(row) + "|")
    lines.append(top)
    return lines

def summarize_bytes(b: bytes) -> str:
    # Friendly digest summary for the info line.
    hexs = b.hex()
    b64 = base64.b64encode(b).decode("ascii")
    if len(hexs) > 64:
        hexs = hexs[:64] + "…"
    if len(b64) > 44:
        b64 = b64[:44] + "…"
    return f"bytes fed to walker: {len(b)} | hex: {hexs} | b64: {b64}"

SCHEMES = {
    "Classic": {
        " ": "#a0a0a0", ".": "#8a8a8a", "o": "#6e6e6e", "+": "#5a5a5a",
        "=": "#3f3f3f", "*": "#1f1f1f", "B": "#8b0000", "O": "#b8860b",
        "X": "#006400", "@": "#00008b", "%": "#4b0082", "&": "#2f4f4f",
        "#": "#000000", "/": "#8b008b", "^": "#2e8b57",
        "|": "#444444", "-": "#444444",
        "S": "#ff8c00", "E": "#dc143c",
    },
    "Neon": {
        " ": "#5c5c5c", ".": "#00ffff", "o": "#00ff7f", "+": "#7fff00",
        "=": "#ffff00", "*": "#ff8c00", "B": "#ff1493", "O": "#ff00ff",
        "X": "#00bfff", "@": "#1e90ff", "%": "#adff2f", "&": "#00ff00",
        "#": "#ffffff", "/": "#ff4500", "^": "#ffd700",
        "|": "#999999", "-": "#999999",
        "S": "#ffffff", "E": "#ff0000",
    },
    "Warm": {
        " ": "#9a9a9a", ".": "#c98c6b", "o": "#d28b4b", "+": "#dd7f2a",
        "=": "#e36b17", "*": "#e65100", "B": "#b71c1c", "O": "#f9a825",
        "X": "#ff6f00", "@": "#4e342e", "%": "#bf360c", "&": "#6d4c41",
        "#": "#3e2723", "/": "#ef6c00", "^": "#ff8f00",
        "|": "#6d6d6d", "-": "#6d6d6d",
        "S": "#ffcc80", "E": "#ff5252",
    },
    "Cool": {
        " ": "#9a9a9a", ".": "#80cbc4", "o": "#4db6ac", "+": "#26a69a",
        "=": "#009688", "*": "#00796b", "B": "#1565c0", "O": "#1e88e5",
        "X": "#3949ab", "@": "#5e35b1", "%": "#00838f", "&": "#006064",
        "#": "#0d47a1", "/": "#283593", "^": "#00acc1",
        "|": "#6d6d6d", "-": "#6d6d6d",
        "S": "#b3e5fc", "E": "#ff5252",
    },
    "Grayscale": {
        " ": "#b0b0b0", ".": "#a0a0a0", "o": "#909090", "+": "#808080",
        "=": "#707070", "*": "#606060", "B": "#505050", "O": "#404040",
        "X": "#303030", "@": "#202020", "%": "#1a1a1a", "&": "#141414",
        "#": "#0e0e0e", "/": "#080808", "^": "#000000",
        "|": "#666666", "-": "#666666",
        "S": "#000000", "E": "#000000",
    }
}

def format_for_symbol(symbol: str, scheme: dict) -> QTextCharFormat:
    # Keep coloring centralized so both views stay in sync.
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(scheme.get(symbol, "#000000")))
    return fmt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Window setup.
        self.setWindowTitle("Drunken Bishop, Painter")
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1200, 760)

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        # Controls
        controls = QGroupBox("Controls")
        root.addWidget(controls)
        form = QGridLayout(controls)

        self.input_text = QLineEdit("hello world")
        self.encoding = QComboBox()
        self.encoding.addItems(["utf-8", "ascii", "latin-1", "utf-16", "utf-32"])

        self.mode = QComboBox()
        self.mode.addItems(["Hash", "Raw bytes"])

        self.hash_name = QComboBox()
        self.hash_name.addItems(["sha256", "sha1", "md5", "blake2b", "blake2s"])

        self.scheme = QComboBox()
        self.scheme.addItems(list(SCHEMES.keys()))

        self.salt = QLineEdit("")
        self.iterations = QSpinBox()
        self.iterations.setRange(1, 1_000_000)
        self.iterations.setValue(1)

        self.width = QSpinBox()
        self.width.setRange(5, 121)
        self.width.setValue(17)

        self.height = QSpinBox()
        self.height.setRange(5, 61)
        self.height.setValue(9)

        self.auto = QCheckBox("Auto-update")
        self.auto.setChecked(True)

        self.walk = QCheckBox("Show walk")
        self.walk.setChecked(False)

        self.walk_time = QSpinBox()
        self.walk_time.setRange(0, 2000)
        self.walk_time.setValue(30)
        self.walk_time.setSuffix(" ms/step")

        self.btn = QPushButton("Generate")
        self.btn.clicked.connect(self.generate)

        # Layout positions
        form.addWidget(QLabel("Input text:"), 0, 0)
        form.addWidget(self.input_text,        0, 1, 1, 7)

        form.addWidget(QLabel("Encoding:"), 1, 0)
        form.addWidget(self.encoding,       1, 1)

        form.addWidget(QLabel("Mode:"),     1, 2)
        form.addWidget(self.mode,           1, 3)

        form.addWidget(QLabel("Hash:"),     1, 4)
        form.addWidget(self.hash_name,      1, 5)

        form.addWidget(QLabel("Scheme:"),   1, 6)
        form.addWidget(self.scheme,         1, 7)

        form.addWidget(QLabel("Salt:"),     2, 0)
        form.addWidget(self.salt,           2, 1)

        form.addWidget(QLabel("Iterations:"), 2, 2)
        form.addWidget(self.iterations,        2, 3)

        form.addWidget(QLabel("Board W:"),  2, 4)
        form.addWidget(self.width,          2, 5)

        form.addWidget(QLabel("Board H:"),  2, 6)
        form.addWidget(self.height,         2, 7)

        form.addWidget(self.btn,            3, 0)
        form.addWidget(self.auto,           3, 1, 1, 2)
        form.addWidget(self.walk,           3, 3, 1, 2)
        form.addWidget(QLabel("Walk time:"), 3, 5)
        form.addWidget(self.walk_time,      3, 6, 1, 2)

        # Info
        self.info = QLabel("")
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.info)

        # Outputs
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, stretch=1)

        self.plain = QTextEdit()
        self.plain.setReadOnly(True)
        self.plain.setLineWrapMode(QTextEdit.NoWrap)
        self.plain.setFont(QFont("Courier New", 12))

        self.colored = QTextEdit()
        self.colored.setReadOnly(True)
        self.colored.setLineWrapMode(QTextEdit.NoWrap)
        self.colored.setFont(QFont("Courier New", 12))

        splitter.addWidget(self.plain)
        splitter.addWidget(self.colored)
        splitter.setSizes([600, 600])

        # Auto-update wiring
        for w in (self.input_text, self.salt):
            w.textChanged.connect(self._maybe_autogen)

        for w in (self.encoding, self.mode, self.hash_name, self.scheme):
            w.currentIndexChanged.connect(self._maybe_autogen)

        for w in (self.iterations, self.width, self.height):
            w.valueChanged.connect(self._maybe_autogen)

        self.auto.stateChanged.connect(self._maybe_autogen)
        self.walk.stateChanged.connect(self._maybe_autogen)
        self.walk_time.valueChanged.connect(self._maybe_autogen)

        self._walk_timer = None
        self._walk_steps = []
        self._walk_index = 0
        self._walk_grid = None
        self._walk_start = None
        self._walk_pos = None
        self._walk_fmt_map = None

        self.generate()

    def _stop_walk(self):
        if self._walk_timer is not None:
            self._walk_timer.stop()
            self._walk_timer.deleteLater()
            self._walk_timer = None

    def _maybe_autogen(self, *_):
        # Skip churn if auto-update is off.
        if self.auto.isChecked():
            self.generate()

    def generate(self):
        self._stop_walk()
        try:
            # Pull current UI state.
            text = self.input_text.text()
            encoding = self.encoding.currentText()
            mode = self.mode.currentText()
            hash_name = self.hash_name.currentText()
            scheme_name = self.scheme.currentText()
            scheme = SCHEMES.get(scheme_name, SCHEMES["Classic"])

            salt_text = self.salt.text()
            salt = bytes_from_string(salt_text, encoding) if salt_text else b""

            iterations = int(self.iterations.value())
            width = int(self.width.value())
            height = int(self.height.value())
            walk_enabled = self.walk.isChecked()

            # Turn input into bytes, then into a walkable buffer.
            raw = bytes_from_string(text, encoding)
            data = derive_bytes(raw, mode, hash_name, salt, iterations)

            self.info.setText(
                f"Input {len(text)} chars | raw {len(raw)} bytes | "
                f"mode={mode} hash={hash_name} salt={len(salt)} iter={iterations} | "
                f"{summarize_bytes(data)}"
            )

            if walk_enabled:
                steps = list(walk_positions(data, width, height))
                grid = [[0] * width for _ in range(height)]
                start_pos = (width // 2, height // 2)
                self._walk_steps = steps
                self._walk_index = 0
                self._walk_grid = grid
                self._walk_start = start_pos
                self._walk_pos = start_pos
                symbols = set(RAMP) | {"S", "E", "|", "-", "+"}
                self._walk_fmt_map = {s: format_for_symbol(s, scheme) for s in symbols}
                self._render_walk()

                interval = int(self.walk_time.value())
                self._walk_timer = QTimer(self)
                self._walk_timer.timeout.connect(self._advance_walk)
                self._walk_timer.start(interval)
            else:
                grid, start_pos, end_pos = build_grid(data, width, height)
                self._render_grid(grid, start_pos, end_pos, scheme)

        except Exception as e:
            messagebox = f"{type(e).__name__}: {e}"
            # Use a Qt-friendly message box
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", messagebox)

    def _advance_walk(self):
        if self._walk_index >= len(self._walk_steps):
            self._stop_walk()
            return

        x, y = self._walk_steps[self._walk_index]
        self._walk_grid[y][x] += 1
        self._walk_pos = (x, y)
        self._walk_index += 1
        self._render_walk()

    def _render_walk(self):
        self._render_grid(self._walk_grid, self._walk_start, self._walk_pos, None)

    def _render_grid(self, grid, start_pos, end_pos, scheme):
        lines = ascii_box_lines(grid, start_pos, end_pos)
        self.plain.setPlainText("\n".join(lines))

        self.colored.clear()
        cursor = self.colored.textCursor()
        cursor.movePosition(QTextCursor.Start)

        if scheme is not None:
            symbols = set(RAMP) | {"S", "E", "|", "-", "+"}
            fmt_map = {s: format_for_symbol(s, scheme) for s in symbols}
        else:
            fmt_map = self._walk_fmt_map

        for line in lines:
            for ch in line:
                cursor.insertText(ch, fmt_map.get(ch, fmt_map[" "]))
            cursor.insertText("\n")

def main():
    # Standard Qt app setup.
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

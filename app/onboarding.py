"""
app/onboarding.py - First-run onboarding window for Numa.

Shown on first launch (no .env file or no GEMINI_API_KEY set).
Walks user through:
  Step 1 - Welcome
  Step 2 - Enter Gemini API key (with link to get one)
  Step 3 - Choose wake word
  Step 4 - Test microphone
  Step 5 - Ready to launch

After completing, writes .env file and relaunches normal startup.
"""

import logging
import os
import sys
import subprocess

from PyQt6.QtCore    import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui     import QFont, QColor, QPixmap, QPainter
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QApplication, QStackedWidget,
    QProgressBar, QSizePolicy
)

from config.settings import settings

logger = logging.getLogger(__name__)


# ── Check if onboarding needed ────────────────────────────────────────────────

def _project_root() -> str:
    """Absolute path to the project root (where main.py lives)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _onboarding_flag_path() -> str:
    """
    Path to the flag file that marks onboarding as complete.
    Stored in AppData so it survives project folder moves.
    """
    appdata = os.environ.get("APPDATA", _project_root())
    folder  = os.path.join(appdata, "Numa")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "onboarding_complete")


def mark_onboarding_complete():
    """Write the flag file. Called after user finishes onboarding."""
    try:
        with open(_onboarding_flag_path(), "w") as f:
            f.write("1")
    except Exception as e:
        logger.error(f"Could not write flag: {e}")


def should_show_onboarding() -> bool:
    """
    Show onboarding if the completion flag file does not exist.
    This is the single source of truth — independent of .env.
    Existing users who already have .env will still see onboarding
    once (until they complete it and the flag is written).
    """
    return not os.path.exists(_onboarding_flag_path())


def force_onboarding():
    """Delete the flag to trigger onboarding on next launch.
    Called from tray menu: Settings > Run Setup Again."""
    flag = _onboarding_flag_path()
    if os.path.exists(flag):
        try:
            os.remove(flag)
        except Exception as e:
            logger.error(f"Could not remove flag: {e}")


# ── Mic test thread ───────────────────────────────────────────────────────────

class MicTestThread(QThread):
    """Runs microphone calibration in background and reports result."""
    result = pyqtSignal(bool, str)   # (success, message)

    def run(self):
        try:
            from speech import calibrate
            calibrate(force=True)
            self.result.emit(True, "Microphone calibrated successfully.")
        except Exception as e:
            self.result.emit(False, f"Mic error: {e}")


# ── Stylesheet ────────────────────────────────────────────────────────────────

_STYLE = """
    QWidget {
        background-color: #FAFAF8;
        font-family: 'Segoe UI';
        color: #2C2C2A;
    }
    QLineEdit {
        background-color: #FFFFFF;
        border: 1.5px solid #D3D1C7;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: #2C2C2A;
    }
    QLineEdit:focus {
        border-color: #2C2C2A;
    }
    QPushButton#primary {
        background-color: #2C2C2A;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 32px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton#primary:hover {
        background-color: #444441;
    }
    QPushButton#primary:disabled {
        background-color: #B4B2A9;
    }
    QPushButton#secondary {
        background-color: transparent;
        border: 1.5px solid #D3D1C7;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 13px;
        color: #888780;
    }
    QPushButton#secondary:hover {
        background-color: #F1EFE8;
    }
    QPushButton#link {
        background: transparent;
        border: none;
        color: #185FA5;
        font-size: 12px;
        padding: 0;
        text-decoration: underline;
    }
    QPushButton#link:hover {
        color: #0C447C;
    }
    QProgressBar {
        border: none;
        background-color: #F1EFE8;
        border-radius: 3px;
        height: 6px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #2C2C2A;
        border-radius: 3px;
    }
"""


# ── Step base ─────────────────────────────────────────────────────────────────

class StepPage(QWidget):
    """Base class for each onboarding step."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def on_enter(self):
        """Called when this step becomes active."""
        pass

    def is_complete(self) -> bool:
        """Return True if user can proceed to next step."""
        return True


# ── Step 1: Welcome ───────────────────────────────────────────────────────────

class WelcomePage(StepPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addStretch()

        # Big N logo
        logo = QLabel("N")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFont(QFont("Segoe UI", 64, QFont.Weight.Bold))
        logo.setStyleSheet("""
            color: white;
            background-color: #2C2C2A;
            border-radius: 24px;
            padding: 8px;
            min-width: 100px;
            max-width: 100px;
            min-height: 100px;
            max-height: 100px;
        """)
        logo.setFixedSize(100, 100)

        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.addStretch()
        logo_layout.addWidget(logo)
        logo_layout.addStretch()
        layout.addWidget(logo_container)

        layout.addSpacing(8)

        title = QLabel("Welcome to Numa")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 26, QFont.Weight.Medium))
        title.setStyleSheet("color: #2C2C2A;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Your personal AI voice assistant for Windows.\n"
            "Let's get you set up in about 2 minutes."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 13))
        subtitle.setStyleSheet("color: #888780; line-height: 1.6;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Feature pills
        features = [
            "Voice-controlled PC",
            "AI powered by Gemini",
            "100% local wake word",
            "Always learning",
        ]
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)
        pills_row.addStretch()
        for f in features:
            pill = QLabel(f)
            pill.setFont(QFont("Segoe UI", 11))
            pill.setStyleSheet("""
                background-color: #F1EFE8;
                color: #444441;
                border-radius: 12px;
                padding: 4px 12px;
            """)
            pills_row.addWidget(pill)
        pills_row.addStretch()
        layout.addLayout(pills_row)

        layout.addStretch()


# ── Step 2: API Key ───────────────────────────────────────────────────────────

class ApiKeyPage(StepPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addStretch()

        title = QLabel("Connect your AI brain")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Medium))
        title.setStyleSheet("color: #2C2C2A;")
        layout.addWidget(title)

        desc = QLabel(
            "Numa uses Google Gemini to understand natural language.\n"
            "It's free to get started — no credit card required."
        )
        desc.setFont(QFont("Segoe UI", 12))
        desc.setStyleSheet("color: #888780;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        # API key input
        key_label = QLabel("Gemini API Key")
        key_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        key_label.setStyleSheet("color: #2C2C2A;")
        layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your API key here...")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.textChanged.connect(self._on_key_changed)
        layout.addWidget(self.key_input)

        # Show/hide toggle
        toggle_row = QHBoxLayout()
        self.show_btn = QPushButton("Show key")
        self.show_btn.setObjectName("link")
        self.show_btn.clicked.connect(self._toggle_visibility)
        toggle_row.addWidget(self.show_btn)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        layout.addSpacing(4)

        # Get key link
        get_key_row = QHBoxLayout()
        get_key_label = QLabel("Don't have a key?")
        get_key_label.setFont(QFont("Segoe UI", 12))
        get_key_label.setStyleSheet("color: #888780;")
        get_key_btn = QPushButton("Get one free at aistudio.google.com →")
        get_key_btn.setObjectName("link")
        get_key_btn.clicked.connect(
            lambda: __import__("webbrowser").open("https://aistudio.google.com/apikey")
        )
        get_key_row.addWidget(get_key_label)
        get_key_row.addWidget(get_key_btn)
        get_key_row.addStretch()
        layout.addLayout(get_key_row)

        # Status label
        self.status = QLabel("")
        self.status.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.status)

        layout.addStretch()

        self._key_visible = False

    def _toggle_visibility(self):
        self._key_visible = not self._key_visible
        if self._key_visible:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_btn.setText("Hide key")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_btn.setText("Show key")

    def _on_key_changed(self, text: str):
        if len(text) > 20:
            self.status.setText("✓ Key looks good — proceed to next step.")
            self.status.setStyleSheet("color: #1D9E75;")
        elif text:
            self.status.setText("Key seems short — double check it.")
            self.status.setStyleSheet("color: #BA7517;")
        else:
            self.status.setText("")

    def get_key(self) -> str:
        return self.key_input.text().strip()

    def is_complete(self) -> bool:
        return len(self.get_key()) > 20


# ── Step 3: Wake Word ─────────────────────────────────────────────────────────

class WakeWordPage(StepPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addStretch()

        title = QLabel("Choose your wake word")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Medium))
        title.setStyleSheet("color: #2C2C2A;")
        layout.addWidget(title)

        desc = QLabel(
            "This is the word you say to activate Numa.\n"
            "Pick one that feels natural to you."
        )
        desc.setFont(QFont("Segoe UI", 12))
        desc.setStyleSheet("color: #888780;")
        layout.addWidget(desc)

        layout.addSpacing(8)

        # Wake word options as large buttons
        options = [
            ("Alexa", "alexa", "Most natural, widely recognized"),
            ("Hey Siri", "hey siri", "Familiar from iPhone"),
            ("OK Google", "ok google", "Familiar from Android"),
        ]

        self._selected = "alexa"
        self._option_btns = {}

        for display, value, hint in options:
            btn_frame = QFrame()
            btn_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_layout = QHBoxLayout(btn_frame)
            btn_layout.setContentsMargins(16, 12, 16, 12)

            text_layout = QVBoxLayout()
            name_lbl = QLabel(display)
            name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
            hint_lbl = QLabel(hint)
            hint_lbl.setFont(QFont("Segoe UI", 11))
            hint_lbl.setStyleSheet("color: #888780;")
            text_layout.addWidget(name_lbl)
            text_layout.addWidget(hint_lbl)

            radio = QLabel("○")
            radio.setFont(QFont("Segoe UI", 16))
            radio.setStyleSheet("color: #D3D1C7;")

            btn_layout.addLayout(text_layout)
            btn_layout.addStretch()
            btn_layout.addWidget(radio)

            self._option_btns[value] = (btn_frame, radio, name_lbl)
            btn_frame.mousePressEvent = lambda e, v=value: self._select(v)
            layout.addWidget(btn_frame)

        # Custom wake word
        custom_label = QLabel("Or type a custom wake word:")
        custom_label.setFont(QFont("Segoe UI", 12))
        custom_label.setStyleSheet("color: #888780; margin-top: 8px;")
        layout.addWidget(custom_label)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("e.g. computer, jarvis, numa...")
        self.custom_input.textChanged.connect(self._on_custom)
        layout.addWidget(self.custom_input)

        layout.addStretch()
        self._select("alexa")

    def _select(self, value: str):
        self._selected = value
        self.custom_input.clear()
        for v, (frame, radio, name) in self._option_btns.items():
            if v == value:
                frame.setStyleSheet("""
                    QFrame {
                        background: #F1EFE8;
                        border: 1.5px solid #2C2C2A;
                        border-radius: 10px;
                    }
                """)
                radio.setText("●")
                radio.setStyleSheet("color: #2C2C2A;")
            else:
                frame.setStyleSheet("""
                    QFrame {
                        background: white;
                        border: 1px solid #D3D1C7;
                        border-radius: 10px;
                    }
                """)
                radio.setText("○")
                radio.setStyleSheet("color: #D3D1C7;")

    def _on_custom(self, text: str):
        if text.strip():
            self._selected = text.strip().lower()
            for _, (frame, radio, _) in self._option_btns.items():
                frame.setStyleSheet("""
                    QFrame {
                        background: white;
                        border: 1px solid #D3D1C7;
                        border-radius: 10px;
                    }
                """)
                radio.setText("○")
                radio.setStyleSheet("color: #D3D1C7;")

    def get_wake_word(self) -> str:
        return self._selected


# ── Step 4: Mic Test ──────────────────────────────────────────────────────────

class MicTestPage(StepPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tested = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addStretch()

        title = QLabel("Test your microphone")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Medium))
        title.setStyleSheet("color: #2C2C2A;")
        layout.addWidget(title)

        desc = QLabel(
            "Numa will calibrate to your mic and room noise.\n"
            "Stay silent for 2 seconds when the test runs."
        )
        desc.setFont(QFont("Segoe UI", 12))
        desc.setStyleSheet("color: #888780;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(16)

        self.test_btn = QPushButton("Test Microphone")
        self.test_btn.setObjectName("primary")
        self.test_btn.setFixedWidth(200)
        self.test_btn.clicked.connect(self._run_test)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.test_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setFixedHeight(6)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.result_label = QLabel("")
        self.result_label.setFont(QFont("Segoe UI", 12))
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        skip_btn = QPushButton("Skip (use defaults)")
        skip_btn.setObjectName("link")
        skip_btn.clicked.connect(self._skip)
        layout.addWidget(skip_btn)

        layout.addStretch()

    def _run_test(self):
        self.test_btn.setEnabled(False)
        self.progress.show()
        self.result_label.setText("Calibrating — stay silent...")
        self.result_label.setStyleSheet("color: #888780;")

        self._thread = MicTestThread()
        self._thread.result.connect(self._on_result)
        self._thread.start()

    def _on_result(self, success: bool, message: str):
        self.progress.hide()
        self.test_btn.setEnabled(True)
        self._tested = True

        if success:
            self.result_label.setText("Microphone ready.")
            self.result_label.setStyleSheet("color: #1D9E75;")
            self.test_btn.setText("Test Again")
        else:
            self.result_label.setText(f"Issue detected: {message}\nYou can still continue.")
            self.result_label.setStyleSheet("color: #BA7517;")

    def _skip(self):
        self._tested = True
        self.result_label.setText("Using default mic settings.")
        self.result_label.setStyleSheet("color: #888780;")

    def is_complete(self) -> bool:
        return self._tested


# ── Step 5: Ready ─────────────────────────────────────────────────────────────

class ReadyPage(StepPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addStretch()

        check = QLabel("✓")
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check.setFont(QFont("Segoe UI", 48))
        check.setStyleSheet("""
            color: white;
            background-color: #1D9E75;
            border-radius: 24px;
            min-width: 80px;
            max-width: 80px;
            min-height: 80px;
            max-height: 80px;
        """)
        check.setFixedSize(80, 80)

        check_container = QWidget()
        cc_layout = QHBoxLayout(check_container)
        cc_layout.addStretch()
        cc_layout.addWidget(check)
        cc_layout.addStretch()
        layout.addWidget(check_container)

        title = QLabel("You're all set!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Medium))
        title.setStyleSheet("color: #2C2C2A;")
        layout.addWidget(title)

        self.wake_word_label = QLabel("")
        self.wake_word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wake_word_label.setFont(QFont("Segoe UI", 13))
        self.wake_word_label.setStyleSheet("color: #888780;")
        layout.addWidget(self.wake_word_label)

        tips_frame = QFrame()
        tips_frame.setStyleSheet("""
            QFrame {
                background: #F1EFE8;
                border-radius: 10px;
                padding: 8px;
            }
        """)
        tips_layout = QVBoxLayout(tips_frame)
        tips_layout.setContentsMargins(16, 12, 16, 12)

        tips_title = QLabel("Quick tips")
        tips_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        tips_title.setStyleSheet("color: #2C2C2A;")
        tips_layout.addWidget(tips_title)

        tips = [
            "Say your wake word + command in one breath",
            "Right-click the tray icon for settings",
            "Double-click tray icon to see conversation",
            "Say 'goodbye' or 'exit' to quit",
        ]
        for tip in tips:
            lbl = QLabel(f"• {tip}")
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet("color: #444441;")
            tips_layout.addWidget(lbl)

        layout.addWidget(tips_frame)
        layout.addStretch()

    def set_wake_word(self, word: str):
        self.wake_word_label.setText(
            f"Say \"{word.title()}\" to wake Numa up."
        )


# ── Main onboarding window ────────────────────────────────────────────────────

class OnboardingWindow(QWidget):

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self._app = app
        self.setWindowTitle("Welcome to Numa")
        self.setMinimumSize(560, 640)
        self.resize(580, 660)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._current_step = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Progress bar ──────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 4)
        self._progress.setValue(0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        # ── Step counter ──────────────────────────────────────────────────
        step_bar = QFrame()
        step_bar.setFixedHeight(40)
        step_bar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #D3D1C7;")
        step_layout = QHBoxLayout(step_bar)
        step_layout.setContentsMargins(24, 0, 24, 0)
        self._step_label = QLabel("Step 1 of 5")
        self._step_label.setFont(QFont("Segoe UI", 11))
        self._step_label.setStyleSheet("color: #888780;")
        step_layout.addWidget(self._step_label)
        step_layout.addStretch()
        root.addWidget(step_bar)

        # ── Pages ─────────────────────────────────────────────────────────
        self._stack = QStackedWidget()

        self._welcome  = WelcomePage()
        self._api_key  = ApiKeyPage()
        self._wake     = WakeWordPage()
        self._mic      = MicTestPage()
        self._ready    = ReadyPage()

        for page in [self._welcome, self._api_key, self._wake, self._mic, self._ready]:
            self._stack.addWidget(page)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 32, 40, 16)
        content_layout.addWidget(self._stack)
        root.addWidget(content, stretch=1)

        # ── Navigation ────────────────────────────────────────────────────
        nav = QFrame()
        nav.setFixedHeight(72)
        nav.setStyleSheet("background: #FFFFFF; border-top: 1px solid #D3D1C7;")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(24, 0, 24, 0)
        nav_layout.setSpacing(12)

        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("secondary")
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.hide()

        self._next_btn = QPushButton("Get Started")
        self._next_btn.setObjectName("primary")
        self._next_btn.clicked.connect(self._go_next)

        nav_layout.addWidget(self._back_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self._next_btn)
        root.addWidget(nav)

    def _go_next(self):
        page = self._stack.currentWidget()

        if not page.is_complete():
            return

        if self._current_step == 4:
            self._finish()
            return

        self._current_step += 1
        self._stack.setCurrentIndex(self._current_step)
        self._progress.setValue(self._current_step)
        self._step_label.setText(f"Step {self._current_step + 1} of 5")
        self._back_btn.show()

        # Update next button label
        labels = ["Get Started", "Next", "Next", "Next", "Launch Numa"]
        self._next_btn.setText(labels[self._current_step])

        # Special: update ready page with chosen wake word
        if self._current_step == 4:
            self._ready.set_wake_word(self._wake.get_wake_word())

        self._stack.currentWidget().on_enter()

    def _go_back(self):
        if self._current_step == 0:
            return
        self._current_step -= 1
        self._stack.setCurrentIndex(self._current_step)
        self._progress.setValue(self._current_step)
        self._step_label.setText(f"Step {self._current_step + 1} of 5")

        if self._current_step == 0:
            self._back_btn.hide()

        labels = ["Get Started", "Next", "Next", "Next", "Launch Numa"]
        self._next_btn.setText(labels[self._current_step])

    def _finish(self):
        """Save settings and write .env file, then relaunch normally."""
        api_key   = self._api_key.get_key()
        wake_word = self._wake.get_wake_word()

        # Write .env file
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".env"
        )
        try:
            # Preserve existing entries, update or add GEMINI_API_KEY
            existing = {}
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if "=" in line and not line.startswith("#"):
                            k, v = line.strip().split("=", 1)
                            existing[k.strip()] = v.strip()
            existing["GEMINI_API_KEY"] = api_key
            with open(env_path, "w") as f:
                for k, v in existing.items():
                    f.write(f"{k}={v}\n")
        except Exception as e:
            logger.error(f"Could not write .env: {e}")

        # Save wake word to settings
        settings.set("wake_word", wake_word)

        # Mark onboarding as complete — won't show again on next launch
        mark_onboarding_complete()

        # Relaunch main app
        self.close()
        subprocess.Popen([sys.executable, "main.py"])
        self._app.quit()
"""
QRYVANTA — Query Intelligence Studio

Fonts
-----
Every theme asks for specific typefaces and falls back through a stack of
common system fonts, so the app always looks decent. For the intended look,
drop these free (OFL) static .ttf files into a ``fonts/`` folder next to this
file; they are loaded automatically at start-up:

    Space Grotesk, Space Mono, Sora, Inter, Orbitron, Rajdhani,
    JetBrains Mono, IBM Plex Mono
"""

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
import json
import copy

import sqlglot
from dotenv import load_dotenv

from PySide6.QtCore import QPointF, QSize, Qt, QProcess, QSettings, Signal, QTimer
from PySide6.QtGui import (
    QColor,
    QIcon,
    QFont,
    QFontDatabase,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QMenu,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from analyzer.analyzer import analyze_query
from database.db import (
    ConnectionProfile,
    clear_active_profile,
    connect_active_profile,
    delete_saved_password,
    get_active_profile,
    get_saved_password,
    save_password,
    test_connection,
)
from core.database import create_adapter
from database_view import DatabaseView
from linter.linter import run_linter
from feature_windows import LearnDialog, HelpDialog, QuizDialog, CompetitiveExamDialog, DeveloperDialog
from export_utils import (export_table_csv, format_command_history, save_report_txt, save_report_pdf, save_report_docx)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

# Development-only compatibility. The application no longer requires
# ORACLE_USER / ORACLE_PASSWORD at import time. Login credentials are
# supplied at runtime and saved through the OS credential store.
SQLPLUS_PATH = os.getenv("SQLPLUS_PATH", "")
ORACLE_USER = os.getenv("ORACLE_USER", "")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/XE")

APP_SETTINGS = QSettings("QRYVANTA", "QRYVANTA")


def resolve_sqlplus_path():
    """Find SQL*Plus for this installation without bundling private .env data.

    Order: environment override, per-user saved setting, PATH, ORACLE_HOME,
    then common Windows Oracle/XE installation locations.
    """
    candidates = []

    env_path = os.getenv("SQLPLUS_PATH", "").strip().strip('"')
    saved_path = str(APP_SETTINGS.value("sqlplus_path", "") or "").strip().strip('"')
    oracle_home = os.getenv("ORACLE_HOME", "").strip().strip('"')

    if env_path:
        candidates.append(env_path)
    if saved_path:
        candidates.append(saved_path)

    for command in ("sqlplus.exe", "sqlplus"):
        found = shutil.which(command)
        if found:
            candidates.append(found)

    if oracle_home:
        candidates.append(str(Path(oracle_home) / "bin" / "sqlplus.exe"))
        candidates.append(str(Path(oracle_home) / "sqlplus.exe"))

    # Common Oracle XE / database installations on Windows.
    candidates.extend([
        r"C:\oraclexe\app\oracle\product\11.2.0\server\bin\sqlplus.exe",
        r"C:\Program Files\Oracle\instantclient\sqlplus.exe",
        r"C:\Program Files (x86)\Oracle\instantclient\sqlplus.exe",
    ])

    for base, pattern in (
        (Path("C:/app"), "*/product/*/dbhome*/bin/sqlplus.exe"),
        (Path("C:/app"), "*/product/*/client*/bin/sqlplus.exe"),
        (Path("C:/oracle"), "*/bin/sqlplus.exe"),
        (Path("C:/Program Files/Oracle"), "*/bin/sqlplus.exe"),
        (Path("C:/Program Files (x86)/Oracle"), "*/bin/sqlplus.exe"),
        (Path("C:/oracle"), "*/product/*/bin/sqlplus.exe"),
    ):
        try:
            candidates.extend(str(path) for path in base.glob(pattern))
        except (OSError, ValueError):
            pass

    seen = set()
    for candidate in candidates:
        expanded = os.path.expandvars(os.path.expanduser(candidate))
        try:
            path = Path(expanded)
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            if path.is_file() and path.name.casefold() == "sqlplus.exe":
                return str(path.resolve())
        except (OSError, ValueError):
            continue

    return ""


# ============================================================
# QRYVANTA THEMES
# ============================================================
#
# Each theme is a complete design system:
#   fonts / scale   typeface stacks (first installed one wins) and a
#                   per-role size multiplier to even out optical size
#   canvas          window, panels, surfaces, ink colours
#   lines           border widths, radii
#   states          hover / active / status-pill colours
#   console / well  dark console and the text wells inside cards
#   cards           one fill / ink / edge colour per analysis card
#   shadow          hard drop shadow (brutalism), soft lift (bento)
#                   or neon glow (cyber themes)
#   syn_*           SQL syntax colours for console and light/dark wells

DISPLAY_SYSTEM = (
    "Segoe UI Variable Display", "Segoe UI Semibold", "SF Pro Display",
    "Helvetica Neue", "Roboto", "Noto Sans", "DejaVu Sans", "Arial",
)
SANS_SYSTEM = (
    "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue",
    "Roboto", "Noto Sans", "DejaVu Sans", "Arial",
)
MONO_SYSTEM = (
    "Cascadia Code", "Cascadia Mono", "SF Mono", "Menlo", "Consolas",
    "DejaVu Sans Mono", "Liberation Mono", "Courier New",
)

CARD_NAMES = (
    "query_card",
    "score_card",
    "complexity_card",
    "lint_card",
    "performance_card",
    "recommendation_card",
)


def card(bg, fg, edge, title=None, big=None, line=None):
    """One analysis card: fill, text, top edge, title colour, score colour."""

    return {
        "bg": bg,
        "fg": fg,
        "edge": edge,
        "title": title or edge,
        "big": big or fg,
        "line": line,
    }


THEMES = {

    # --------------------------------------------------------
    # Loud, flat, honest. Cream paper, black ink, hard shadows.
    # --------------------------------------------------------
    "01 · NEO-BRUTALISM": {
        "fonts": {
            "display": ("Space Grotesk", "Archivo") + DISPLAY_SYSTEM,
            "body": ("Space Grotesk", "Archivo") + SANS_SYSTEM,
            "mono": ("Space Mono", "JetBrains Mono") + MONO_SYSTEM,
        },
        "scale": {"display": 1.0, "body": 1.0, "mono": 1.0},

        "bg": "#FAF1DE",
        "panel": "#F2E5C8",
        "panel_bw": 3,
        "analysis_bg": "#FAF1DE",
        "analysis_bw": 3,
        "surface": "#FFFFFF",
        "surface_2": "#F2E5C8",
        "ink": "#0A0A0A",
        "muted": "#4C4639",

        "line": "#0A0A0A",
        "line_soft": "#CDBF9F",
        "border_width": 3,
        "radius": 0,
        "inner_radius": 0,
        "pill_radius": 0,

        "accent": "#FF5C93",
        "accent_ink": "#0A0A0A",
        "hover_bg": "#FFD23F",
        "hover_fg": "#0A0A0A",
        "hover_line": "#0A0A0A",
        "active_bg": "#FF5C93",
        "active_fg": "#0A0A0A",
        "active_line": "#0A0A0A",

        "ok_bg": "#B8F34A", "ok_fg": "#0A0A0A",
        "warn_bg": "#FFD23F", "warn_fg": "#0A0A0A",
        "bad_bg": "#FF6B6B", "bad_fg": "#0A0A0A",

        "console_bg": "#121212",
        "console_fg": "#F6EFE0",
        "console_line": "#0A0A0A",
        "console_scroll": "#6B6556",
        "console_scroll_hover": "#B8F34A",
        "input_edge": "#FF5C93",

        "well_bg": "#FFFFFF",
        "well_fg": "#0A0A0A",
        "well_line": "#0A0A0A",
        "well_bw": 2,

        "selection": "#6D4AFF",
        "selection_fg": "#FFFFFF",

        "th_bg": "#FFD23F",
        "th_fg": "#0A0A0A",
        "th_line": "#0A0A0A",

        "scroll_track": "#F2E5C8",
        "scroll_handle": "#0A0A0A",
        "scroll_hover": "#FF5C93",
        "scroll_radius": 0,
        "handle_hover": "#FF5C93",

        "card_bw": 3,
        "card_line": "#0A0A0A",
        "edge_w": 3,
        "cards": {
            "query_card": card("#FFD23F", "#0A0A0A", "#0A0A0A"),
            "score_card": card("#B8F34A", "#0A0A0A", "#0A0A0A"),
            "complexity_card": card("#7DC4FF", "#0A0A0A", "#0A0A0A"),
            "lint_card": card("#FF8FB8", "#0A0A0A", "#0A0A0A"),
            "performance_card": card("#FFA94D", "#0A0A0A", "#0A0A0A"),
            "recommendation_card": card("#C9B6FF", "#0A0A0A", "#0A0A0A"),
        },
        "shadow": {"dx": 5, "dy": 5, "blur": 0, "color": "#0A0A0A",
                   "alpha": 255, "use_edge": False},

        "syn_console": {
            "kw": "#FF7DAE", "fn": "#7DC4FF", "str": "#B8F34A",
            "num": "#FFD23F", "cmt": "#8F8878", "op": "#FFA94D",
            "prompt": "#B8F34A", "bad": "#FF6B6B", "warn": "#FFD23F",
            "info": "#7DC4FF", "good": "#B8F34A",
        },
        "syn_well": {
            "kw": "#C2185B", "fn": "#0B5CAD", "str": "#18732E",
            "num": "#B34700", "cmt": "#7A7466", "op": "#B34700",
            "prompt": "#18732E", "bad": "#C62828", "warn": "#9A6B00",
            "info": "#0B5CAD", "good": "#18732E",
        },
    },

    # --------------------------------------------------------
    # Deep navy glass, cyan signal, violet and lime accents.
    # --------------------------------------------------------
    "02 · CYBERCORE": {
        "fonts": {
            "display": ("Sora", "Exo 2", "Bahnschrift") + DISPLAY_SYSTEM,
            "body": ("Inter",) + SANS_SYSTEM,
            "mono": ("JetBrains Mono", "Fira Code") + MONO_SYSTEM,
        },
        "scale": {"display": 0.95, "body": 1.0, "mono": 1.0},

        "bg": "#060A12",
        "panel": "#0A111E",
        "panel_bw": 1,
        "analysis_bg": "#060A12",
        "analysis_bw": 1,
        "surface": "#0E1626",
        "surface_2": "#121C30",
        "ink": "#E8F2FF",
        "muted": "#7F93B2",

        "line": "#1C3050",
        "line_soft": "#16253F",
        "border_width": 1,
        "radius": 12,
        "inner_radius": 8,
        "pill_radius": 10,

        "accent": "#2DE2E6",
        "accent_ink": "#031317",
        "hover_bg": "#10283A",
        "hover_fg": "#2DE2E6",
        "hover_line": "#2DE2E6",
        "active_bg": "#2DE2E6",
        "active_fg": "#031317",
        "active_line": "#2DE2E6",

        "ok_bg": "#0C3A33", "ok_fg": "#4DF0C2",
        "warn_bg": "#3D3110", "warn_fg": "#FFC857",
        "bad_bg": "#43121F", "bad_fg": "#FF6B8E",

        "console_bg": "#04070D",
        "console_fg": "#CFE6FF",
        "console_line": "#1C3050",
        "console_scroll": "#22385A",
        "console_scroll_hover": "#2DE2E6",
        "input_edge": "#2DE2E6",

        "well_bg": "#070D18",
        "well_fg": "#D6E6FA",
        "well_line": "#182A45",
        "well_bw": 1,

        "selection": "#8B6CFF",
        "selection_fg": "#FFFFFF",

        "th_bg": "#101B31",
        "th_fg": "#2DE2E6",
        "th_line": "#1C3050",

        "scroll_track": "#0A111E",
        "scroll_handle": "#22385A",
        "scroll_hover": "#2DE2E6",
        "scroll_radius": 3,
        "handle_hover": "#1F4466",

        "card_bw": 1,
        "card_line": "#1C3050",
        "edge_w": 3,
        "cards": {
            "query_card": card("#0D1526", "#D6E6FA", "#2DE2E6"),
            "score_card": card("#0D1526", "#D6E6FA", "#B8FF5C"),
            "complexity_card": card("#0D1526", "#D6E6FA", "#8B6CFF"),
            "lint_card": card("#0D1526", "#D6E6FA", "#FF5C8A"),
            "performance_card": card("#0D1526", "#D6E6FA", "#FFC857"),
            "recommendation_card": card("#0D1526", "#D6E6FA", "#4D8DFF"),
        },
        "shadow": {"dx": 0, "dy": 0, "blur": 28, "color": "#000000",
                   "alpha": 70, "use_edge": True},

        "syn_console": {
            "kw": "#9D82FF", "fn": "#2DE2E6", "str": "#B8FF5C",
            "num": "#FFC857", "cmt": "#4F6585", "op": "#FF5C8A",
            "prompt": "#2DE2E6", "bad": "#FF6B8E", "warn": "#FFC857",
            "info": "#5CA8FF", "good": "#4DF0C2",
        },
        "syn_well": {
            "kw": "#9D82FF", "fn": "#2DE2E6", "str": "#B8FF5C",
            "num": "#FFC857", "cmt": "#4F6585", "op": "#FF5C8A",
            "prompt": "#2DE2E6", "bad": "#FF6B8E", "warn": "#FFC857",
            "info": "#5CA8FF", "good": "#4DF0C2",
        },
    },

    # --------------------------------------------------------
    # International Typographic Style. Paper, black, one red.
    # --------------------------------------------------------
    "03 · SWISS": {
        "fonts": {
            "display": ("Helvetica Neue", "Helvetica", "Neue Haas Grotesk Text Pro",
                        "Inter", "Arial", "Liberation Sans", "Nimbus Sans",
                        "DejaVu Sans"),
            "body": ("Helvetica Neue", "Helvetica", "Neue Haas Grotesk Text Pro",
                     "Inter", "Arial", "Liberation Sans", "Nimbus Sans",
                     "DejaVu Sans"),
            "mono": ("IBM Plex Mono", "JetBrains Mono") + MONO_SYSTEM,
        },
        "scale": {"display": 1.0, "body": 1.0, "mono": 1.0},

        "bg": "#F3F2EE",
        "panel": "#F3F2EE",
        "panel_bw": 0,
        "analysis_bg": "#F3F2EE",
        "analysis_bw": 0,
        "surface": "#FFFFFF",
        "surface_2": "#E9E8E2",
        "ink": "#0B0B0B",
        "muted": "#66655F",

        "line": "#0B0B0B",
        "line_soft": "#CFCEC6",
        "border_width": 2,
        "radius": 0,
        "inner_radius": 0,
        "pill_radius": 0,

        "accent": "#E10600",
        "accent_ink": "#FFFFFF",
        "hover_bg": "#0B0B0B",
        "hover_fg": "#FFFFFF",
        "hover_line": "#0B0B0B",
        "active_bg": "#E10600",
        "active_fg": "#FFFFFF",
        "active_line": "#E10600",

        "ok_bg": "#0B0B0B", "ok_fg": "#FFFFFF",
        "warn_bg": "#F2C230", "warn_fg": "#0B0B0B",
        "bad_bg": "#E10600", "bad_fg": "#FFFFFF",

        "console_bg": "#0B0B0B",
        "console_fg": "#F3F2EE",
        "console_line": "#0B0B0B",
        "console_scroll": "#55554F",
        "console_scroll_hover": "#E10600",
        "input_edge": "#E10600",

        "well_bg": "#F3F2EE",
        "well_fg": "#0B0B0B",
        "well_line": "#CFCEC6",
        "well_bw": 1,

        "selection": "#E10600",
        "selection_fg": "#FFFFFF",

        "th_bg": "#0B0B0B",
        "th_fg": "#FFFFFF",
        "th_line": "#0B0B0B",

        "scroll_track": "#E9E8E2",
        "scroll_handle": "#0B0B0B",
        "scroll_hover": "#E10600",
        "scroll_radius": 0,
        "handle_hover": "#E10600",

        "card_bw": 2,
        "card_line": "#0B0B0B",
        "edge_w": 6,
        "cards": {
            "query_card": card("#FFFFFF", "#0B0B0B", "#0B0B0B"),
            "score_card": card("#E10600", "#FFFFFF", "#0B0B0B",
                               title="#FFFFFF", big="#FFFFFF"),
            "complexity_card": card("#FFFFFF", "#0B0B0B", "#0B0B0B"),
            "lint_card": card("#FFFFFF", "#0B0B0B", "#E10600",
                              title="#0B0B0B"),
            "performance_card": card("#FFFFFF", "#0B0B0B", "#0B0B0B"),
            "recommendation_card": card("#FFFFFF", "#0B0B0B", "#0B0B0B"),
        },
        "shadow": None,

        "syn_console": {
            "kw": "#FF5A4D", "fn": "#8FB0FF", "str": "#E4E3DC",
            "num": "#F2C230", "cmt": "#77766F", "op": "#FF5A4D",
            "prompt": "#FF5A4D", "bad": "#FF5A4D", "warn": "#F2C230",
            "info": "#8FB0FF", "good": "#7FD99A",
        },
        "syn_well": {
            "kw": "#C70F00", "fn": "#1F3FFF", "str": "#3B3A36",
            "num": "#8A5A00", "cmt": "#8D8C85", "op": "#C70F00",
            "prompt": "#C70F00", "bad": "#C70F00", "warn": "#8A5A00",
            "info": "#1F3FFF", "good": "#1B7F3A",
        },
    },

    # --------------------------------------------------------
    # Soft pastel tiles, generous radii, gentle lift.
    # --------------------------------------------------------
    "04 · BENTO GRID": {
        "fonts": {
            "display": ("Inter Display", "Inter") + DISPLAY_SYSTEM,
            "body": ("Inter",) + SANS_SYSTEM,
            "mono": ("JetBrains Mono", "IBM Plex Mono") + MONO_SYSTEM,
        },
        "scale": {"display": 1.0, "body": 1.0, "mono": 1.0},

        "bg": "#EBEEF4",
        "panel": "#FFFFFF",
        "panel_bw": 1,
        "analysis_bg": "#EBEEF4",
        "analysis_bw": 0,
        "surface": "#FFFFFF",
        "surface_2": "#F3F5F9",
        "ink": "#161D31",
        "muted": "#69738C",

        "line": "#D9DEEA",
        "line_soft": "#E6EAF2",
        "border_width": 1,
        "radius": 20,
        "inner_radius": 12,
        "pill_radius": 14,

        "accent": "#6C5CE7",
        "accent_ink": "#FFFFFF",
        "hover_bg": "#EFEDFF",
        "hover_fg": "#4A3CC4",
        "hover_line": "#6C5CE7",
        "active_bg": "#6C5CE7",
        "active_fg": "#FFFFFF",
        "active_line": "#6C5CE7",

        "ok_bg": "#DDF5E6", "ok_fg": "#12794A",
        "warn_bg": "#FFF1CC", "warn_fg": "#8A5F00",
        "bad_bg": "#FFE0E8", "bad_fg": "#B52A52",

        "console_bg": "#131A2C",
        "console_fg": "#E9EFFF",
        "console_line": "#131A2C",
        "console_scroll": "#33405F",
        "console_scroll_hover": "#8F82FF",
        "input_edge": "#6C5CE7",

        "well_bg": "#FFFFFF",
        "well_fg": "#161D31",
        "well_line": "#DDE2EE",
        "well_bw": 1,

        "selection": "#6C5CE7",
        "selection_fg": "#FFFFFF",

        "th_bg": "#F0EEFF",
        "th_fg": "#4A3CC4",
        "th_line": "#E1DEF8",

        "scroll_track": "#F3F5F9",
        "scroll_handle": "#C5CBDB",
        "scroll_hover": "#6C5CE7",
        "scroll_radius": 3,
        "handle_hover": "#D9D4FF",

        "card_bw": 1,
        "card_line": "#DDE2EE",
        "edge_w": 1,
        "cards": {
            "query_card": card("#EAE6FF", "#161D31", "#D3CEFA",
                               title="#4A3CC4", line="#D3CEFA"),
            "score_card": card("#DFF6E8", "#161D31", "#C2E8D1",
                               title="#12794A", big="#12794A", line="#C2E8D1"),
            "complexity_card": card("#DCEEFF", "#161D31", "#C3DFF7",
                                    title="#1766B3", line="#C3DFF7"),
            "lint_card": card("#FFE3EA", "#161D31", "#F7C6D3",
                              title="#B52A52", line="#F7C6D3"),
            "performance_card": card("#FFEBDB", "#161D31", "#F6D3B9",
                                     title="#B4560F", line="#F6D3B9"),
            "recommendation_card": card("#FFF6D0", "#161D31", "#EFE0A0",
                                        title="#7A5C00", line="#EFE0A0"),
        },
        "shadow": {"dx": 0, "dy": 8, "blur": 26, "color": "#3A4A8A",
                   "alpha": 38, "use_edge": False},

        "syn_console": {
            "kw": "#B1A6FF", "fn": "#74D3FF", "str": "#82E3AB",
            "num": "#FFCB7E", "cmt": "#6A7899", "op": "#FF93B1",
            "prompt": "#82E3AB", "bad": "#FF8FA8", "warn": "#FFCB7E",
            "info": "#74D3FF", "good": "#82E3AB",
        },
        "syn_well": {
            "kw": "#5B49D9", "fn": "#1766B3", "str": "#12794A",
            "num": "#B4560F", "cmt": "#8A94AD", "op": "#B52A52",
            "prompt": "#5B49D9", "bad": "#B52A52", "warn": "#8A5F00",
            "info": "#1766B3", "good": "#12794A",
        },
    },

    # --------------------------------------------------------
    # Night city. Magenta, cyan and yellow neon on violet black.
    # --------------------------------------------------------
    "05 · CYBERPUNK": {
        "fonts": {
            "display": ("Orbitron", "Audiowide", "Bahnschrift") + DISPLAY_SYSTEM,
            "body": ("Rajdhani", "Chakra Petch", "Bahnschrift",
                     "Roboto Condensed") + SANS_SYSTEM,
            "mono": ("JetBrains Mono", "Share Tech Mono") + MONO_SYSTEM,
        },
        "scale": {"display": 0.78, "body": 1.12, "mono": 1.0},

        "bg": "#08040F",
        "panel": "#0E0718",
        "panel_bw": 1,
        "analysis_bg": "#08040F",
        "analysis_bw": 1,
        "surface": "#130A22",
        "surface_2": "#1A0E2E",
        "ink": "#F5EEFF",
        "muted": "#A58BC9",

        "line": "#3F1B66",
        "line_soft": "#2A1348",
        "border_width": 1,
        "radius": 3,
        "inner_radius": 2,
        "pill_radius": 2,

        "accent": "#FF2E97",
        "accent_ink": "#0A0412",
        "hover_bg": "#2A0F3C",
        "hover_fg": "#00F0FF",
        "hover_line": "#00F0FF",
        "active_bg": "#FF2E97",
        "active_fg": "#0A0412",
        "active_line": "#FF2E97",

        "ok_bg": "#06302F", "ok_fg": "#00F0FF",
        "warn_bg": "#3A3305", "warn_fg": "#FCEE0A",
        "bad_bg": "#40081F", "bad_fg": "#FF4D8D",

        "console_bg": "#05030A",
        "console_fg": "#EADFFF",
        "console_line": "#FF2E97",
        "console_scroll": "#3B2160",
        "console_scroll_hover": "#FF2E97",
        "input_edge": "#00F0FF",

        "well_bg": "#09050F",
        "well_fg": "#EADFFF",
        "well_line": "#2D1750",
        "well_bw": 1,

        "selection": "#00F0FF",
        "selection_fg": "#05030A",

        "th_bg": "#1F1036",
        "th_fg": "#00F0FF",
        "th_line": "#4B1F7A",

        "scroll_track": "#0E0718",
        "scroll_handle": "#4B1F7A",
        "scroll_hover": "#FF2E97",
        "scroll_radius": 2,
        "handle_hover": "#FF2E97",

        "card_bw": 1,
        "card_line": "#3A1A5E",
        "edge_w": 3,
        "cards": {
            "query_card": card("#110920", "#EADFFF", "#00F0FF"),
            "score_card": card("#110920", "#EADFFF", "#FCEE0A"),
            "complexity_card": card("#110920", "#EADFFF", "#9D5CFF"),
            "lint_card": card("#110920", "#EADFFF", "#FF2E97"),
            "performance_card": card("#110920", "#EADFFF", "#FF7A18"),
            "recommendation_card": card("#110920", "#EADFFF", "#2BFF9A"),
        },
        "shadow": {"dx": 0, "dy": 0, "blur": 24, "color": "#000000",
                   "alpha": 105, "use_edge": True},

        "syn_console": {
            "kw": "#FF2E97", "fn": "#00F0FF", "str": "#FCEE0A",
            "num": "#FF7A18", "cmt": "#6E5A91", "op": "#9D5CFF",
            "prompt": "#00F0FF", "bad": "#FF4D8D", "warn": "#FCEE0A",
            "info": "#00F0FF", "good": "#2BFF9A",
        },
        "syn_well": {
            "kw": "#FF2E97", "fn": "#00F0FF", "str": "#FCEE0A",
            "num": "#FF7A18", "cmt": "#6E5A91", "op": "#9D5CFF",
            "prompt": "#00F0FF", "bad": "#FF4D8D", "warn": "#FCEE0A",
            "info": "#00F0FF", "good": "#2BFF9A",
        },
    },
}


def theme_variant(theme, night_mode=False):
    """Apply a legible shared day/night palette without losing theme accents/type."""
    t = copy.deepcopy(theme)
    if night_mode:
        palette = {
            "bg": "#0B1020", "panel": "#10192B", "analysis_bg": "#0B1020",
            "surface": "#111B2E", "surface_2": "#1A2942", "ink": "#EEF4FF",
            "muted": "#B1BED2", "line": "#344661", "line_soft": "#293B56",
            "console_bg": "#070B14", "console_fg": "#E8F0FF", "console_line": "#344661",
            "console_scroll": "#435574", "well_bg": "#0D1525", "well_fg": "#E8F0FF",
            "well_line": "#344661", "hover_bg": "#1A2942", "hover_fg": "#EEF4FF",
            "active_bg": t["accent"], "active_fg": t.get("accent_ink", "#08101F"),
            "active_line": t["accent"], "hover_line": t["accent"], "input_edge": t["accent"],
            "selection": t["accent"], "selection_fg": t.get("accent_ink", "#08101F"),
            "ok_bg": "#123D32", "ok_fg": "#91F0C5", "warn_bg": "#44350B",
            "warn_fg": "#FFDA72", "bad_bg": "#4C1C2A", "bad_fg": "#FF99AB",
            "th_bg": "#1A2942", "th_fg": "#EEF4FF", "th_line": "#344661",
            "scroll_track": "#111B2E", "scroll_handle": "#435574", "scroll_hover": t["accent"],
            "handle_hover": t["accent"], "card_line": "#344661",
        }
        t["shadow"] = "none" if isinstance(t.get("shadow"), str) else t.get("shadow")
        t["syn_console"] = {"kw":"#B6B7FF","fn":"#7FE1FF","str":"#95E6B5","num":"#FFD17A","cmt":"#8291AB","op":"#FF91B6","prompt":t["accent"],"bad":"#FF99AB","warn":"#FFDA72","info":"#7FE1FF","good":"#91F0C5"}
        t["syn_well"] = dict(t["syn_console"])
    else:
        palette = {
            "bg": "#F5F7FB", "panel": "#ECF1F8", "analysis_bg": "#F5F7FB",
            "surface": "#FFFFFF", "surface_2": "#EAF0F7", "ink": "#182337",
            "muted": "#526176", "line": "#CBD5E1", "line_soft": "#DDE5EF",
            "console_bg": "#101827", "console_fg": "#F2F6FF", "console_line": "#344661",
            "console_scroll": "#536782", "well_bg": "#FFFFFF", "well_fg": "#182337",
            "well_line": "#CBD5E1", "hover_bg": "#EEF3FA", "hover_fg": "#182337",
            "active_bg": t["accent"], "active_fg": t.get("accent_ink", "#FFFFFF"),
            "active_line": t["accent"], "hover_line": t["accent"], "input_edge": t["accent"],
            "selection": t["accent"], "selection_fg": t.get("accent_ink", "#FFFFFF"),
            "ok_bg": "#DDF5E6", "ok_fg": "#12643F", "warn_bg": "#FFF1CC",
            "warn_fg": "#735000", "bad_bg": "#FFE0E8", "bad_fg": "#9A2348",
            "th_bg": "#EAF0F7", "th_fg": "#182337", "th_line": "#CBD5E1",
            "scroll_track": "#EAF0F7", "scroll_handle": "#A4B1C4", "scroll_hover": t["accent"],
            "handle_hover": t["accent"], "card_line": "#CBD5E1",
        }
        t["syn_console"] = {"kw":"#B6B7FF","fn":"#7FE1FF","str":"#95E6B5","num":"#FFD17A","cmt":"#8291AB","op":"#FF91B6","prompt":t["accent"],"bad":"#FF99AB","warn":"#FFDA72","info":"#7FE1FF","good":"#91F0C5"}
        t["syn_well"] = {"kw":"#5144B5","fn":"#1766B3","str":"#14734A","num":"#8A5700","cmt":"#69778B","op":"#B4235A","prompt":t["accent"],"bad":"#B4233C","warn":"#8A5F00","info":"#1766B3","good":"#14734A"}
    t.update(palette)
    t["well_bw"] = max(1, int(t.get("well_bw", 1)))
    t["cards"] = {name: {**values, "bg": t["surface"], "fg": t["ink"], "title": t["accent"], "big": t["ink"], "edge": t["accent"], "line": t["line"]} for name, values in t["cards"].items()}
    return t


def validate_themes():
    """Fail early (and clearly) if a theme is missing a design token."""

    reference_name = next(iter(THEMES))
    reference = set(THEMES[reference_name])

    for name, theme in THEMES.items():

        missing = reference - set(theme)
        extra = set(theme) - reference

        if missing or extra:
            raise KeyError(
                f"Theme '{name}' does not match '{reference_name}': "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )

        for card_name in CARD_NAMES:
            if card_name not in theme["cards"]:
                raise KeyError(f"Theme '{name}' has no '{card_name}'")


validate_themes()


# ============================================================
# TYPOGRAPHY
# ============================================================

FONT_DIR = Path(__file__).resolve().parent / "fonts"

WEIGHTS = {
    "regular": QFont.Weight.Normal,
    "medium": QFont.Weight.Medium,
    "semibold": QFont.Weight.DemiBold,
    "bold": QFont.Weight.Bold,
    "extrabold": QFont.Weight.ExtraBold,
    "black": QFont.Weight.Black,
}

# objectName -> (family role, pixel size, weight, letter spacing)
ROLE_FONTS = {
    "main_logo": ("display", 30, "extrabold", 3.0),
    "tagline": ("body", 10, "semibold", 2.4),
    "theme_label": ("body", 10, "bold", 2.2),
    "header_button": ("body", 11, "bold", 1.4),
    "theme_selector": ("body", 11, "bold", 1.0),
    "panel_title": ("display", 15, "bold", 2.4),
    "connection": ("mono", 10, "bold", 1.0),
    "account_status": ("mono", 10, "bold", 1.0),
    "live": ("mono", 10, "bold", 1.0),
    "sqlens_logo": ("display", 20, "extrabold", 2.6),
    "subtitle": ("body", 10, "semibold", 2.2),
    "card_title": ("body", 10, "bold", 2.2),
    "score": ("display", 62, "extrabold", 0.0),
    "score_suffix": ("body", 11, "semibold", 1.6),
    "complexity": ("mono", 12, "medium", 0.0),
    "analysis_text": ("mono", 12, "regular", 0.0),
    "sql_console": ("mono", 13, "regular", 0.0),
    "sql_input": ("mono", 13, "regular", 0.0),
    "status": ("mono", 11, "semibold", 1.0),
    "db_title": ("display", 24, "extrabold", 2.0),
    "db_section": ("body", 10, "bold", 2.2),
    "db_selected_table": ("display", 19, "bold", 0.5),
    "db_info": ("body", 12, "medium", 0.0),
}

_family_index = None


def load_bundled_fonts():
    """Register every .ttf / .otf found in ./fonts with Qt."""

    global _family_index

    loaded = []

    if FONT_DIR.is_dir():
        for path in sorted(FONT_DIR.rglob("*")):
            if path.suffix.lower() in (".ttf", ".otf"):
                if QFontDatabase.addApplicationFont(str(path)) != -1:
                    loaded.append(path.name)

    _family_index = None

    return loaded


def installed_families():

    global _family_index

    if _family_index is None:
        _family_index = {
            family.lower(): family
            for family in QFontDatabase.families()
        }

    return _family_index


def pick_family(stack, fixed=False):
    """First family of the stack that is actually installed."""

    index = installed_families()

    for name in stack:
        hit = index.get(name.lower())
        if hit:
            return hit

    kind = (
        QFontDatabase.SystemFont.FixedFont
        if fixed
        else QFontDatabase.SystemFont.GeneralFont
    )

    return QFontDatabase.systemFont(kind).family()


def resolve_fonts(theme):

    return {
        "display": pick_family(theme["fonts"]["display"]),
        "body": pick_family(theme["fonts"]["body"]),
        "mono": pick_family(theme["fonts"]["mono"], fixed=True),
    }


def make_font(fonts, scale, kind, px, weight="regular", tracking=0.0):

    font = QFont(fonts[kind])

    font.setPixelSize(max(9, round(px * scale[kind])))
    font.setWeight(WEIGHTS[weight])
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

    if tracking:
        font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            tracking,
        )

    return font


def apply_typography(root, theme, fonts, database_view):
    """Set every themed font. QSS carries colour only."""

    scale = theme["scale"]

    for widget in root.findChildren(QWidget):

        role = ROLE_FONTS.get(widget.objectName())

        if role:
            widget.setFont(make_font(fonts, scale, *role))

    # Database view: widgets without object names are styled by class.

    for item_list in database_view.findChildren(QListWidget):
        item_list.setFont(make_font(fonts, scale, "body", 13, "semibold"))

    for table in database_view.findChildren(QTableWidget):
        table.setFont(make_font(fonts, scale, "mono", 12, "regular"))
        table.horizontalHeader().setFont(
            make_font(fonts, scale, "body", 11, "bold", 1.2)
        )
        table.verticalHeader().setFont(
            make_font(fonts, scale, "mono", 11, "regular")
        )

    for button in database_view.findChildren(QPushButton):
        button.setFont(make_font(fonts, scale, "body", 11, "bold", 1.2))
        button.setCursor(Qt.PointingHandCursor)


# ============================================================
# THEME HELPERS
# ============================================================

def build_palette(theme):
    """Application palette, so even unstyled widgets match the theme."""

    palette = QPalette()

    roles = {
        QPalette.ColorRole.Window: theme["bg"],
        QPalette.ColorRole.WindowText: theme["ink"],
        QPalette.ColorRole.Base: theme["surface"],
        QPalette.ColorRole.AlternateBase: theme["surface_2"],
        QPalette.ColorRole.Text: theme["ink"],
        QPalette.ColorRole.Button: theme["surface"],
        QPalette.ColorRole.ButtonText: theme["ink"],
        QPalette.ColorRole.Highlight: theme["selection"],
        QPalette.ColorRole.HighlightedText: theme["selection_fg"],
        QPalette.ColorRole.ToolTipBase: theme["surface"],
        QPalette.ColorRole.ToolTipText: theme["ink"],
        QPalette.ColorRole.PlaceholderText: theme["muted"],
        QPalette.ColorRole.Link: theme["accent"],
    }

    for role, color in roles.items():
        palette.setColor(role, QColor(color))

    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            role,
            QColor(theme["muted"]),
        )

    return palette


def chevron_path(color):
    """Render a small chevron PNG (for the combo box) in a theme colour."""

    folder = Path(tempfile.gettempdir()) / "qryvanta_assets"
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"chevron_{color.lstrip('#')}.png"

    if not path.exists():

        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(color))
        pen.setWidthF(2.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        painter.drawPolyline(
            QPolygonF([
                QPointF(6, 9),
                QPointF(12, 15),
                QPointF(18, 9),
            ])
        )

        painter.end()
        pixmap.save(str(path))

    return path.as_posix()


def repolish(widget):
    """Re-evaluate QSS after a dynamic property changed."""

    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def scrollbar_css(prefix, track, handle, hover, radius, thick=11):

    p = f"{prefix} " if prefix else ""

    return f"""
    {p}QScrollBar:vertical {{
        background: {track}; width: {thick}px; margin: 0; border: none;
    }}
    {p}QScrollBar::handle:vertical {{
        background: {handle}; min-height: 34px; margin: 2px;
        border-radius: {radius}px;
    }}
    {p}QScrollBar::handle:vertical:hover {{ background: {hover}; }}
    {p}QScrollBar:horizontal {{
        background: {track}; height: {thick}px; margin: 0; border: none;
    }}
    {p}QScrollBar::handle:horizontal {{
        background: {handle}; min-width: 34px; margin: 2px;
        border-radius: {radius}px;
    }}
    {p}QScrollBar::handle:horizontal:hover {{ background: {hover}; }}
    {p}QScrollBar::add-line, {p}QScrollBar::sub-line {{
        width: 0; height: 0; background: none; border: none;
    }}
    {p}QScrollBar::add-page, {p}QScrollBar::sub-page {{ background: none; }}
    """


def build_stylesheet(t, arrow):
    """Main window stylesheet. Colour, borders and radii only."""

    bw = t["border_width"]
    r = t["radius"]
    ir = t["inner_radius"]
    pr = t["pill_radius"]

    ink, muted, line = t["ink"], t["muted"], t["line"]
    surface = t["surface"]

    # Brutalist / Swiss pills wear the heavy border; soft themes
    # tint the border with the state colour instead.
    def pill_border(fg):
        return line if bw >= 2 else fg

    css = [f"""
    QMainWindow, #central {{ background-color: {t["bg"]}; }}

    QLabel {{ background: transparent; color: {ink}; }}

    QToolTip {{
        background-color: {surface}; color: {ink};
        border: {bw}px solid {line}; padding: 6px 8px;
    }}

    QLineEdit {{
        background-color: {surface}; color: {ink};
        border: {max(1, bw - 1)}px solid {line};
        border-radius: {ir}px; padding: 6px 10px;
        selection-background-color: {t["selection"]};
        selection-color: {t["selection_fg"]};
    }}
    QLineEdit:focus {{ border-color: {t["accent"]}; }}

    /* ---------- header ---------- */

    #main_logo {{ color: {ink}; }}
    #tagline, #theme_label, #subtitle {{ color: {muted}; }}
    #panel_title, #sqlens_logo {{ color: {ink}; }}

    #header_button {{
        background-color: {surface}; color: {ink};
        border: {bw}px solid {line}; border-radius: {r}px;
        padding: 8px 14px;
    }}
    #header_button:hover {{
        background-color: {t["hover_bg"]}; color: {t["hover_fg"]};
        border-color: {t["hover_line"]};
    }}
    #header_button:pressed, #header_button[active="true"] {{
        background-color: {t["active_bg"]}; color: {t["active_fg"]};
        border-color: {t["active_line"]};
    }}

    #theme_selector {{
        background-color: {surface}; color: {ink};
        border: {bw}px solid {line}; border-radius: {r}px;
        padding: 7px 36px 7px 14px; min-width: 190px;
    }}
    #theme_selector:hover, #theme_selector:on {{
        border-color: {t["hover_line"]};
    }}
    #theme_selector::drop-down {{
        subcontrol-origin: padding; subcontrol-position: center right;
        width: 32px; border: none; background: transparent;
    }}
    #theme_selector::down-arrow {{
        image: url("{arrow}"); width: 14px; height: 14px;
    }}
    #theme_selector QAbstractItemView {{
        background-color: {surface}; color: {ink};
        border: {bw}px solid {line}; border-radius: 0px;
        padding: 4px; outline: 0;
        selection-background-color: {t["active_bg"]};
        selection-color: {t["active_fg"]};
    }}
    #theme_selector QAbstractItemView::item {{
        min-height: 30px; padding: 0 8px;
    }}

    /* ---------- panels ---------- */

    #sqlplus_panel {{
        background-color: {t["panel"]};
        border: {t["panel_bw"]}px solid {line}; border-radius: {r}px;
    }}
    #analysis_panel {{
        background-color: {t["analysis_bg"]};
        border: {t["analysis_bw"]}px solid {line}; border-radius: {r}px;
    }}

    /* ---------- status pills ---------- */

    #connection, #live {{
        background-color: {t["ok_bg"]}; color: {t["ok_fg"]};
        border: {bw}px solid {pill_border(t["ok_fg"])};
        border-radius: {pr}px; padding: 5px 12px;
    }}
    #account_status {{
        background-color: {t["ok_bg"]}; color: {t["ok_fg"]};
        border: {bw}px solid {pill_border(t["ok_fg"])};
        border-radius: {pr}px; padding: 5px 12px;
    }}
    #account_status[state="wait"] {{
        background-color: {t["warn_bg"]}; color: {t["warn_fg"]};
        border-color: {pill_border(t["warn_fg"])};
    }}
    #account_status[state="bad"] {{
        background-color: {t["bad_bg"]}; color: {t["bad_fg"]};
        border-color: {pill_border(t["bad_fg"])};
    }}
    #connection[state="wait"] {{
        background-color: {t["warn_bg"]}; color: {t["warn_fg"]};
        border-color: {pill_border(t["warn_fg"])};
    }}
    #connection[state="bad"] {{
        background-color: {t["bad_bg"]}; color: {t["bad_fg"]};
        border-color: {pill_border(t["bad_fg"])};
    }}

    #status {{
        background-color: {surface}; color: {ink};
        border: {bw}px solid {line}; border-radius: {r}px;
        padding: 8px 14px;
    }}

    /* ---------- console ---------- */

    QPlainTextEdit#sql_console {{
        background-color: {t["console_bg"]}; color: {t["console_fg"]};
        border: {bw}px solid {t["console_line"]}; border-radius: {r}px;
        padding: 12px;
        selection-background-color: {t["selection"]};
        selection-color: {t["selection_fg"]};
    }}

    QPlainTextEdit#sql_input {{
        background-color: {t["console_bg"]}; color: {t["console_fg"]};
        border: {bw}px solid {t["console_line"]};
        border-top: {max(2, bw + 1)}px solid {t["input_edge"]};
        border-radius: {r}px; padding: 10px;
        selection-background-color: {t["selection"]};
        selection-color: {t["selection_fg"]};
    }}
    QPlainTextEdit#sql_input:focus {{ border-color: {t["accent"]}; }}

    /* ---------- cards ---------- */
    """]

    card_bw = t["card_bw"]

    for name, c in t["cards"].items():

        card_line = c["line"] or t["card_line"]

        css.append(f"""
    #{name} {{
        background-color: {c["bg"]};
        border: {card_bw}px solid {card_line};
        border-top: {t["edge_w"]}px solid {c["edge"]};
        border-radius: {r}px;
    }}
    #{name} QLabel#card_title {{ color: {c["title"]}; }}
    #{name} QLabel#complexity {{ color: {c["fg"]}; }}
    #{name} QLabel#score {{ color: {c["big"]}; }}
    #{name} QLabel#score_suffix {{ color: {c["title"]}; }}
    """)

    css.append(f"""
    QPlainTextEdit#analysis_text {{
        background-color: {t["well_bg"]}; color: {t["well_fg"]};
        border: {t["well_bw"]}px solid {t["well_line"]};
        border-radius: {ir}px; padding: 8px 10px;
        selection-background-color: {t["selection"]};
        selection-color: {t["selection_fg"]};
    }}

    /* ---------- splitter ---------- */

    QSplitter::handle {{ background-color: transparent; }}
    QSplitter::handle:hover {{ background-color: {t["handle_hover"]}; }}
    """)

    sr = t["scroll_radius"]

    css.append(scrollbar_css(
        "", t["scroll_track"], t["scroll_handle"], t["scroll_hover"], sr))

    for selector in ("#sql_console", "#sql_input"):
        css.append(scrollbar_css(
            selector, t["console_bg"], t["console_scroll"],
            t["console_scroll_hover"], sr))

    css.append(scrollbar_css(
        "QPlainTextEdit#analysis_text", t["well_bg"], t["scroll_handle"],
        t["scroll_hover"], sr))

    return "\n".join(css)


def build_database_stylesheet(t):
    """Stylesheet for the database view (object names owned by DatabaseView)."""

    bw = t["border_width"]
    r = t["radius"]
    ir = t["inner_radius"]
    inner_bw = max(1, bw - 1)

    ink, muted, line = t["ink"], t["muted"], t["line"]

    return f"""
    #db_title, #db_selected_table {{ color: {ink}; }}
    #db_section, #db_info {{ color: {muted}; }}

    #db_table_panel, #db_data_panel {{
        background-color: {t["surface"]};
        border: {bw}px solid {line}; border-radius: {r}px;
    }}

    QListWidget {{
        background-color: {t["surface_2"]}; color: {ink};
        border: {inner_bw}px solid {t["line_soft"]};
        border-radius: {ir}px; padding: 4px; outline: 0;
    }}
    QListWidget::item {{
        color: {ink}; background-color: transparent;
        padding: 9px 10px; margin: 1px 0;
        border-radius: {max(0, ir - 2)}px;
    }}
    QListWidget::item:hover {{
        background-color: {t["hover_bg"]}; color: {t["hover_fg"]};
    }}
    QListWidget::item:selected {{
        background-color: {t["active_bg"]}; color: {t["active_fg"]};
    }}

    QTableWidget {{
        background-color: {t["surface"]}; color: {ink};
        border: {inner_bw}px solid {t["line_soft"]};
        gridline-color: {t["line_soft"]}; outline: 0;
        selection-background-color: {t["selection"]};
        selection-color: {t["selection_fg"]};
    }}
    QTableWidget::item {{ color: {ink}; background-color: {t["surface"]}; padding: 4px; }}
    QTableWidget::item:alternate {{ color: {ink}; background-color: {t["surface_2"]}; }}
    QTableWidget::item:selected {{
        background-color: {t["selection"]}; color: {t["selection_fg"]};
    }}

    QHeaderView::section {{
        background-color: {t["th_bg"]}; color: {t["th_fg"]};
        border: none; border-right: 1px solid {t["th_line"]};
        border-bottom: {bw}px solid {t["th_line"]};
        padding: 8px 10px;
    }}
    QTableCornerButton::section {{ background-color: {t["th_bg"]}; border: none; }}

    QPushButton {{
        background-color: {t["surface"]}; color: {ink};
        border: {bw}px solid {line}; border-radius: {r}px;
        padding: 8px 14px;
    }}
    QPushButton:hover {{
        background-color: {t["hover_bg"]}; color: {t["hover_fg"]};
        border-color: {t["hover_line"]};
    }}
    QPushButton:pressed {{
        background-color: {t["active_bg"]}; color: {t["active_fg"]};
        border-color: {t["active_line"]};
    }}
    """


# ============================================================
# SQL HELPERS
# ============================================================

def statement_complete(text):
    """
    Detect a semicolon outside quoted strings.
    """

    single_quote = False
    double_quote = False

    i = 0

    while i < len(text):
        char = text[i]

        if char == "'" and not double_quote:

            # Oracle escaped quote: ''
            if (
                i + 1 < len(text)
                and text[i + 1] == "'"
            ):
                i += 2
                continue

            single_quote = not single_quote

        elif char == '"' and not single_quote:

            double_quote = not double_quote

        i += 1

    if single_quote or double_quote:
        return False

    return text.rstrip().endswith(";")


def is_sql_statement(text):
    """
    Determine whether the captured text looks like
    an SQL statement that QRYVANTA should analyze.
    """

    cleaned = text.strip().upper()

    keywords = (
        "SELECT ",
        "WITH ",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "MERGE ",
        "CREATE ",
        "ALTER ",
        "DROP ",
        "TRUNCATE ",
    )

    return cleaned.startswith(keywords)


# ============================================================
# SYNTAX HIGHLIGHTING
# ============================================================

SQL_KEYWORDS = """
SELECT FROM WHERE GROUP BY ORDER HAVING JOIN INNER LEFT RIGHT FULL OUTER
CROSS NATURAL ON USING AS AND OR NOT IN IS NULL LIKE BETWEEN EXISTS ANY SOME
ALL DISTINCT UNIQUE UNION INTERSECT MINUS CASE WHEN THEN ELSE END INSERT INTO
VALUES UPDATE SET DELETE MERGE MATCHED CREATE ALTER DROP TRUNCATE TABLE VIEW
INDEX PRIMARY KEY FOREIGN REFERENCES CONSTRAINT DEFAULT CHECK ADD COLUMN
MODIFY WITH FETCH FIRST NEXT ROWS ONLY OFFSET ASC DESC OVER PARTITION
CONNECT PRIOR START LEVEL ROWNUM ROWID DUAL SEQUENCE TRIGGER BEGIN DECLARE
COMMIT ROLLBACK SAVEPOINT GRANT REVOKE TO
""".split()

SQL_FUNCTIONS = """
COUNT SUM AVG MIN MAX NVL NVL2 COALESCE NULLIF DECODE TO_CHAR TO_DATE
TO_NUMBER TO_TIMESTAMP SUBSTR INSTR LENGTH UPPER LOWER INITCAP TRIM LTRIM
RTRIM LPAD RPAD REPLACE CONCAT ROUND TRUNC ABS CEIL FLOOR MOD POWER SYSDATE
SYSTIMESTAMP CURRENT_DATE LISTAGG ROW_NUMBER RANK DENSE_RANK LAG LEAD CAST
EXTRACT ADD_MONTHS MONTHS_BETWEEN LAST_DAY
""".split()

SQL_TOKEN_RE = re.compile(
    r"""
      (?P<cmt>--[^\n]*)
    | (?P<str>'(?:[^']|'')*(?:'|$))
    | (?P<id>"[^"\n]*"?)
    | (?P<num>\b\d+(?:\.\d+)?\b)
    | (?P<fn>\b(?:""" + "|".join(SQL_FUNCTIONS) + r""")\b(?=\s*\())
    | (?P<kw>\b(?:""" + "|".join(SQL_KEYWORDS) + r""")\b)
    | (?P<op>[=<>!+\-*/%|]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)


class SQLHighlighter(QSyntaxHighlighter):
    """SQL colouring for the input box and the analysed-query box."""

    def __init__(self, document):

        super().__init__(document)

        self.formats = {}

    @staticmethod
    def make_format(color, bold=False, italic=False):

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))

        if bold:
            fmt.setFontWeight(700)

        if italic:
            fmt.setFontItalic(True)

        return fmt

    def set_colors(self, colors):

        make = self.make_format

        self.formats = {
            "kw": make(colors["kw"], bold=True),
            "fn": make(colors["fn"]),
            "str": make(colors["str"]),
            "id": make(colors["fn"]),
            "num": make(colors["num"]),
            "op": make(colors["op"]),
            "cmt": make(colors["cmt"], italic=True),
            "prompt": make(colors["prompt"], bold=True),
            "bad": make(colors["bad"], bold=True),
            "warn": make(colors["warn"], bold=True),
            "info": make(colors["info"], bold=True),
            "good": make(colors["good"], bold=True),
            "dim": make(colors["cmt"]),
        }

        self.rehighlight()

    def sql_tokens(self, text, start=0):

        for match in SQL_TOKEN_RE.finditer(text, start):
            self.setFormat(
                match.start(),
                match.end() - match.start(),
                self.formats[match.lastgroup],
            )

    def block_comments(self, text):

        in_comment = self.previousBlockState() == 1

        pos = 0 if in_comment else text.find("/*")

        while pos >= 0:

            search_from = pos if in_comment else pos + 2
            end = text.find("*/", search_from)

            if end < 0:
                self.setCurrentBlockState(1)
                self.setFormat(pos, len(text) - pos, self.formats["cmt"])
                return

            length = end + 2 - pos
            self.setFormat(pos, length, self.formats["cmt"])

            in_comment = False
            pos = text.find("/*", pos + length)

    def highlightBlock(self, text):

        if not self.formats:
            return

        self.setCurrentBlockState(0)
        self.sql_tokens(text)
        self.block_comments(text)


class ConsoleHighlighter(SQLHighlighter):
    """SQL*Plus transcript: prompts, echoed SQL, errors, success lines."""

    PROMPT_RE = re.compile(r"^\s*SQL>\s?")

    OUTPUT_RULES = [
        (re.compile(r"(?:ORA|SP2|TNS|PLS)-\d{3,5}.*", re.I), "bad"),
        (re.compile(r"^ERROR( at line \d+)?:?.*", re.I), "bad"),
        (re.compile(r"^\[SQL\*PLUS ERROR\].*"), "bad"),
        (re.compile(r"^\s*(?:\d+|no) rows? (?:selected|created|updated|"
                    r"deleted|merged)\.?", re.I), "good"),
        (re.compile(r"^(?:(?:Table|Index|View|Sequence|Trigger|Procedure|"
                    r"Function|Package|Synonym|Type) (?:created|altered|"
                    r"dropped|truncated)\.|Commit complete\.|Connected\.|"
                    r"PL/SQL procedure successfully completed\.|"
                    r"Statement processed\.)", re.I), "good"),
        (re.compile(r"^[-\s]{5,}$"), "dim"),
        (re.compile(r"^(?:SQL\*Plus: Release|Copyright|Connected to:|"
                    r"Oracle Database|Version ).*", re.I), "dim"),
    ]

    def highlightBlock(self, text):

        if not self.formats:
            return

        self.setCurrentBlockState(0)

        if not text.strip():
            return

        prompt = self.PROMPT_RE.match(text)

        if prompt:

            self.setFormat(0, prompt.end(), self.formats["prompt"])
            self.sql_tokens(text, prompt.end())

            if not text.rstrip().endswith(";"):
                self.setCurrentBlockState(2)

            return

        if self.previousBlockState() == 2:

            self.sql_tokens(text)

            if not text.rstrip().endswith(";"):
                self.setCurrentBlockState(2)

            return

        for pattern, key in self.OUTPUT_RULES:
            for match in pattern.finditer(text):
                self.setFormat(
                    match.start(),
                    match.end() - match.start(),
                    self.formats[key],
                )


class FindingsHighlighter(SQLHighlighter):
    """Lint / performance / recommendation text: severity-aware colours."""

    RULE_LINE_RE = re.compile(r"^(\S+)\s+\[([^\]]*)\]\s*$")

    @staticmethod
    def severity_key(word):

        w = word.lower()

        if any(k in w for k in ("crit", "high", "error", "severe", "fatal")):
            return "bad"

        if any(k in w for k in ("warn", "med", "moder")):
            return "warn"

        return "info"

    def highlightBlock(self, text):

        if not self.formats:
            return

        self.setCurrentBlockState(0)

        stripped = text.strip()

        if not stripped:
            return

        if stripped.startswith("✓"):
            self.setFormat(0, len(text), self.formats["good"])
            return

        if stripped.startswith("ANALYSIS ERROR"):
            self.setFormat(0, len(text), self.formats["bad"])
            return

        rule = self.RULE_LINE_RE.match(text)

        if rule:
            self.setFormat(
                rule.start(1),
                rule.end(1) - rule.start(1),
                self.formats["kw"],
            )
            self.setFormat(
                rule.start(2) - 1,
                rule.end(2) - rule.start(2) + 2,
                self.formats[self.severity_key(rule.group(2))],
            )
            return

        if text.startswith("TYPE:"):
            self.setFormat(0, 5, self.formats["dim"])
            self.setFormat(5, len(text) - 5, self.formats["info"])
            return

        if text.startswith("SQL:"):
            self.setFormat(0, 4, self.formats["dim"])
            self.sql_tokens(text, 4)


# ============================================================
# SQL INPUT
# ============================================================

class SQLInput(QPlainTextEdit):

    submitted = Signal(str)
    history_up = Signal()
    history_down = Signal()

    def __init__(self):
        super().__init__()

        self.setObjectName("sql_input")

        self.setFixedHeight(92)

        self.setPlaceholderText("SQL>  Type your Oracle SQL here...")

        self.highlighter = SQLHighlighter(self.document())

    def apply_theme(self, theme):

        colors = theme["syn_console"]

        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.PlaceholderText,
            QColor(colors["cmt"]),
        )
        self.setPalette(palette)

        self.highlighter.set_colors(colors)

    def keyPressEvent(self, event):

        key = event.key()
        modifiers = event.modifiers()

        # Shift + Enter = new line
        if (
            key in (
                Qt.Key_Return,
                Qt.Key_Enter,
            )
            and modifiers & Qt.ShiftModifier
        ):
            QPlainTextEdit.keyPressEvent(self, event)
            return

        # Enter = send
        if key in (
            Qt.Key_Return,
            Qt.Key_Enter,
        ):
            self.submitted.emit(self.toPlainText())
            self.clear()
            return

        # Up
        if key == Qt.Key_Up:
            self.history_up.emit()
            return

        # Down
        if key == Qt.Key_Down:
            self.history_down.emit()
            return

        QPlainTextEdit.keyPressEvent(self, event)


# ============================================================
# CONNECTION / ACCOUNT DIALOGS
# ============================================================

def _saved_profiles():
    raw = APP_SETTINGS.value("saved_profiles", "[]")

    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        data = []

    profiles = []

    for item in data:
        try:
            profiles.append(
                ConnectionProfile.from_dict(item)
            )
        except (KeyError, TypeError, ValueError):
            continue

    return profiles


def _write_saved_profiles(profiles):
    APP_SETTINGS.setValue(
        "saved_profiles",
        json.dumps(
            [profile.to_dict() for profile in profiles]
        )
    )
    APP_SETTINGS.sync()


def _upsert_saved_profile(profile):
    profiles = _saved_profiles()

    replaced = False
    for index, existing in enumerate(profiles):
        if existing.keyring_service == profile.keyring_service:
            profiles[index] = profile
            replaced = True
            break

    if not replaced:
        profiles.append(profile)

    _write_saved_profiles(profiles)


def _remove_saved_profile(profile):
    profiles = [
        existing
        for existing in _saved_profiles()
        if existing.keyring_service != profile.keyring_service
    ]

    _write_saved_profiles(profiles)
    delete_saved_password(profile)


def _profile_key(profile):
    return profile.keyring_service


def _environment_profile():
    """
    Development convenience only.

    Prefills the login dialog from the existing .env file when available.
    The password is never persisted here by QRYVANTA itself.
    """

    if not ORACLE_USER:
        return None

    host = "localhost"
    port = 1521
    service = "XE"

    dsn = ORACLE_DSN.strip()

    try:
        if "/" in dsn:
            host_port, service = dsn.split("/", 1)

            if ":" in host_port:
                host, port_text = host_port.rsplit(":", 1)
                port = int(port_text)
            else:
                host = host_port

        elif ":" in dsn:
            host, port_text = dsn.rsplit(":", 1)
            port = int(port_text)

        return ConnectionProfile(
            database_type="oracle",
            host=host,
            port=port,
            database=service,
            username=ORACLE_USER,
            profile_name="Development Oracle",
        )

    except (TypeError, ValueError):
        return None


class DatabaseLoginDialog(QDialog):

    def __init__(
        self,
        theme,
        parent=None,
        initial_profile=None,
        new_profile=False,
        force_remember=False,
    ):

        super().__init__(parent)

        self.theme = theme
        self.profile = None
        self.password = ""
        self.new_profile = bool(new_profile)
        self.force_remember = bool(force_remember)
        self.saved_profiles = _saved_profiles()

        self.setWindowTitle("QRYVANTA — Database Login")
        self.setMinimumWidth(600)
        self.setModal(True)

        self.setup_ui(initial_profile)
        self.apply_theme(theme)

    def setup_ui(self, initial_profile):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(
            "ADD DATABASE ACCOUNT" if self.new_profile else "DATABASE LOGIN"
        )
        title.setObjectName("db_title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Save a connection and sign in to Oracle, MySQL, or PostgreSQL. "
            "Saved passwords stay in your operating-system credential store."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("db_info")
        layout.addWidget(subtitle)

        # Saved-account controls are intentionally collapsed on first open.
        # The normal form remains the default path for creating/connecting a
        # new account. Returning users can reveal saved profiles on demand.
        self.saved_accounts_button = None
        if not self.new_profile:
            self.saved_accounts_button = QPushButton("SAVED ACCOUNTS")
            self.saved_accounts_button.setObjectName("header_button")
            self.saved_accounts_button.setCursor(Qt.PointingHandCursor)
            self.saved_accounts_button.clicked.connect(
                self.toggle_saved_accounts
            )
            layout.addWidget(self.saved_accounts_button, alignment=Qt.AlignLeft)

        self.saved_account_row = QWidget()
        saved_layout = QHBoxLayout(self.saved_account_row)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(8)

        self.saved_profile_combo = QComboBox()
        self.saved_profile_combo.setObjectName("saved_account_selector")
        self.saved_profile_combo.addItem("Choose a saved account…", "")

        if not self.saved_profiles:
            self.saved_profile_combo.addItem("No saved accounts yet", "")
            self.saved_profile_combo.setEnabled(False)
        else:
            for saved_profile in self.saved_profiles:
                label = (
                    f"{saved_profile.profile_name}  •  "
                    f"{saved_profile.database_type.upper()}  •  "
                    f"{saved_profile.username}@{saved_profile.host}"
                )
                self.saved_profile_combo.addItem(
                    label,
                    saved_profile.keyring_service,
                )

        self.login_saved_button = QPushButton("LOGIN TO SAVED")
        self.login_saved_button.setObjectName("header_button")
        self.login_saved_button.setCursor(Qt.PointingHandCursor)
        self.login_saved_button.clicked.connect(
            self.login_selected_saved_profile
        )

        saved_layout.addWidget(self.saved_profile_combo, 1)
        saved_layout.addWidget(self.login_saved_button)
        self.saved_account_row.hide()

        if not self.new_profile:
            layout.addWidget(self.saved_account_row)

        self.login_saved_button.setEnabled(bool(self.saved_profiles))

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.database_combo = QComboBox()
        self.database_combo.addItems(["Oracle", "MySQL", "PostgreSQL"])
        self.database_combo.setCurrentIndex(0)

        self.host_edit = QLineEdit()
        self.port_edit = QLineEdit()
        self.database_edit = QLineEdit()
        self.username_edit = QLineEdit()

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        self.profile_name_edit = QLineEdit()

        self.remember_check = QCheckBox(
            "Remember this account on this computer"
        )
        self.remember_check.setChecked(True)

        if self.force_remember:
            self.remember_check.setChecked(True)
            self.remember_check.setEnabled(False)
            self.remember_check.setText(
                "Save this account for future sign-ins"
            )

        form.addRow("Database", self.database_combo)
        form.addRow("Host", self.host_edit)
        form.addRow("Port", self.port_edit)
        form.addRow("Service / Database", self.database_edit)
        form.addRow("Username", self.username_edit)
        form.addRow("Password", self.password_edit)
        form.addRow("Account name", self.profile_name_edit)

        layout.addLayout(form)
        layout.addWidget(self.remember_check)

        self.help_label = QLabel(
            "QRYVANTA connects through the selected database's native adapter."
        )
        self.help_label.setWordWrap(True)
        self.help_label.setObjectName("db_info")
        layout.addWidget(self.help_label)

        buttons = QDialogButtonBox()
        self.test_button = buttons.addButton(
            "TEST CONNECTION",
            QDialogButtonBox.ActionRole,
        )
        self.login_button = buttons.addButton(
            "LOGIN",
            QDialogButtonBox.AcceptRole,
        )
        self.cancel_button = buttons.addButton(
            "CANCEL",
            QDialogButtonBox.RejectRole,
        )

        self.test_button.clicked.connect(self.test_current_connection)
        self.login_button.clicked.connect(self.login)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._last_database_default = None
        self.database_combo.currentTextChanged.connect(
            self.database_type_changed
        )

        profile = initial_profile
        if profile is None and not self.new_profile:
            profile = _environment_profile()

        if profile is not None:
            self.set_profile(profile)
            saved_password = get_saved_password(profile)
            if saved_password:
                self.password_edit.setText(saved_password)
            elif (
                not self.new_profile
                and initial_profile is None
                and profile.database_type == "oracle"
                and ORACLE_PASSWORD
            ):
                # Development-only convenience for the original .env profile.
                self.password_edit.setText(ORACLE_PASSWORD)
        else:
            self.host_edit.setText("localhost")
            self.database_type_changed(self.database_combo.currentText())

        self.database_type_changed(
            self.database_combo.currentText()
        )

        if self.new_profile:
            self.host_edit.setText("localhost")
            self.database_edit.clear()
            self.username_edit.clear()
            self.password_edit.clear()
            self.profile_name_edit.clear()
            self.profile_name_edit.setPlaceholderText("e.g. College MySQL")

    def toggle_saved_accounts(self):
        """Reveal/hide saved profiles only when the user asks for them."""
        if self.new_profile:
            return

        is_open = self.saved_account_row.isVisible()
        show_saved = not is_open
        self.saved_account_row.setVisible(show_saved)

        if self.saved_accounts_button is not None:
            self.saved_accounts_button.setText(
                "HIDE SAVED ACCOUNTS" if show_saved else "SAVED ACCOUNTS"
            )

        if show_saved and self.saved_profiles:
            self.saved_profile_combo.setFocus()

    def selected_saved_profile(self):

        key = self.saved_profile_combo.currentData()
        if not key:
            return None

        for profile in self.saved_profiles:
            if profile.keyring_service == key:
                return profile

        return None

    def load_saved_profile(self, profile):

        self.set_profile(profile)
        password = get_saved_password(profile)
        self.password_edit.setText(password or "")

        if not password:
            QMessageBox.information(
                self,
                "Password Required",
                "This saved account has no password stored. Enter its password "
                "below, then click LOGIN.",
            )
            self.password_edit.setFocus()

    def login_selected_saved_profile(self):

        profile = self.selected_saved_profile()
        if profile is None:
            QMessageBox.information(
                self,
                "Choose a Saved Account",
                "Select an account from the saved-account list first.",
            )
            return

        password = get_saved_password(profile)
        if not password:
            self.load_saved_profile(profile)
            return

        success, message = test_connection(profile, password)
        if not success:
            # Still load the connection details so the user can re-enter a
            # changed password or correct the connection details.
            self.load_saved_profile(profile)
            QMessageBox.warning(
                self,
                "Saved Login Failed",
                f"Could not sign in to '{profile.profile_name}'.\n\n{message}\n\n"
                "Check the password or connection details, then use LOGIN.",
            )
            return

        self.profile = profile
        self.password = password
        self.remember_check.setChecked(True)
        self.accept()

    def set_profile(self, profile):

        display_name = (
            "PostgreSQL"
            if profile.database_type == "postgres"
            else profile.database_type.capitalize()
        )

        index = self.database_combo.findText(display_name)
        if index >= 0:
            self.database_combo.setCurrentIndex(index)

        self.host_edit.setText(profile.host)
        self.port_edit.setText(str(profile.port))
        self.database_edit.setText(profile.database)
        self.username_edit.setText(profile.username)
        self.profile_name_edit.setText(profile.profile_name)

        saved_index = self.saved_profile_combo.findData(
            profile.keyring_service
        )
        if saved_index >= 0:
            self.saved_profile_combo.setCurrentIndex(saved_index)

    def database_type_changed(self, database_name):

        defaults = {
            "Oracle": (1521, "XE / service name"),
            "MySQL": (3306, "database name"),
            "PostgreSQL": (5432, "database name"),
        }
        default_port, placeholder = defaults.get(
            database_name,
            (1521, "database name"),
        )

        current_port = self.port_edit.text().strip()
        if not current_port or current_port == str(self._last_database_default):
            self.port_edit.setText(str(default_port))
        self._last_database_default = default_port

        self.database_edit.setPlaceholderText(placeholder)
        if database_name == "Oracle":
            self.help_label.setText(
                "Oracle XE/Oracle Database connection. Oracle 11g uses "
                "python-oracledb Thick mode with Oracle Client libraries."
            )
        elif database_name == "MySQL":
            self.help_label.setText(
                "MySQL uses QRYVANTA's native connector for execution, "
                "schema browsing, SQL dialect handling, and EXPLAIN."
            )
        else:
            self.help_label.setText(
                "PostgreSQL uses QRYVANTA's native connector for execution, "
                "schema browsing, SQL dialect handling, and EXPLAIN."
            )

    def make_profile(self):

        database_type = self.database_combo.currentText().strip().lower()
        if database_type == "postgresql":
            database_type = "postgres"

        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            raise ValueError("Port must be a number.")

        profile_name = self.profile_name_edit.text().strip()
        if not profile_name:
            profile_name = (
                f"{self.database_combo.currentText()} - "
                f"{self.username_edit.text().strip()}@"
                f"{self.host_edit.text().strip()}"
            )

        return ConnectionProfile(
            database_type=database_type,
            host=self.host_edit.text(),
            port=port,
            database=self.database_edit.text(),
            username=self.username_edit.text(),
            profile_name=profile_name,
        )

    def current_password(self):
        return self.password_edit.text()

    def test_current_connection(self):

        try:
            profile = self.make_profile()
            password = self.current_password()
            if not password:
                raise ValueError("Password cannot be empty.")

            success, message = test_connection(profile, password)
            if success:
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    f"Connected successfully to:\n\n{profile.profile_name}",
                )
            else:
                QMessageBox.critical(self, "Connection Failed", message)

        except Exception as error:
            QMessageBox.critical(self, "Connection Failed", str(error))

    def login(self):

        try:
            profile = self.make_profile()
            password = self.current_password()
            if not password:
                raise ValueError("Password cannot be empty.")

            success, message = test_connection(profile, password)
            if not success:
                QMessageBox.critical(self, "Login Failed", message)
                return

            if self.remember_check.isChecked():
                save_password(profile, password)
                _upsert_saved_profile(profile)

            self.profile = profile
            self.password = password
            self.accept()

        except Exception as error:
            QMessageBox.critical(self, "Login Failed", str(error))

    def apply_theme(self, theme):

        self.theme = theme
        self.setStyleSheet(
            build_stylesheet(theme, chevron_path(theme["ink"]))
        )

        fonts = resolve_fonts(theme)
        apply_typography(
            self,
            theme,
            fonts,
            self.parent().database_view
            if self.parent() and hasattr(self.parent(), "database_view")
            else QWidget(),
        )


class AccountCardWidget(QFrame):
    """A readable, compact card for one saved database profile."""

    def __init__(self, profile, is_active, theme, parent=None):
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMinimumHeight(68)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        name = QLabel(profile.profile_name or "Unnamed account")
        name.setObjectName("account_card_name")
        name.setMinimumWidth(90)
        top.addWidget(name, 1)

        db_type = QLabel(profile.database_type.upper())
        db_type.setObjectName("account_type_badge")
        top.addWidget(db_type, 0, Qt.AlignmentFlag.AlignRight)

        state = QLabel("✓ CONNECTED" if is_active else "SAVED")
        state.setObjectName("account_state_badge")
        top.addWidget(state, 0, Qt.AlignmentFlag.AlignRight)

        outer.addLayout(top)

        target_text = (
            f"{profile.username}@{profile.host}:{profile.port}/"
            f"{profile.database}"
        )
        target = QLabel(target_text)
        target.setObjectName("account_card_target")
        target.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        outer.addWidget(target)

        self.set_visual_state(theme, selected=False)

    def set_visual_state(self, theme, selected=False):
        background = theme["surface_2"] if selected else theme["surface"]
        outline = theme["accent"] if selected else theme["line"]
        border_width = 2 if selected else 1
        radius = max(6, int(theme["radius"]))
        self.setStyleSheet(f"""
            QFrame#account_card {{
                background-color: {background};
                border: {border_width}px solid {outline};
                border-left: 5px solid {theme['accent']};
                border-radius: {radius}px;
            }}
            QLabel#account_card_name {{
                color: {theme['ink']}; background: transparent;
                border: none; font-weight: 700; font-size: 12px;
            }}
            QLabel#account_card_target {{
                color: {theme['muted']}; background: transparent;
                border: none; font-size: 10px;
            }}
            QLabel#account_type_badge {{
                color: {theme['accent']}; background: {theme['well_bg']};
                border: 1px solid {theme['line']}; border-radius: 7px;
                padding: 3px 7px; font-size: 9px; font-weight: 700;
            }}
            QLabel#account_state_badge {{
                color: {theme['ok_fg'] if 'CONNECTED' in self.findChild(QLabel, 'account_state_badge').text() else theme['muted']};
                background: {theme['ok_bg'] if 'CONNECTED' in self.findChild(QLabel, 'account_state_badge').text() else theme['well_bg']};
                border: 1px solid {theme['line']}; border-radius: 7px;
                padding: 3px 7px; font-size: 9px; font-weight: 700;
            }}
        """)


class AccountSwitcherDialog(QDialog):

    def __init__(self, theme, profiles, parent=None):

        super().__init__(parent)

        self.theme = theme
        self.profiles = list(profiles)
        self.selected_profile = None
        self.added_profile = None
        self.added_password = ""
        self.account_cards = []

        self.setWindowTitle("QRYVANTA — Switch Account")
        self.setMinimumSize(820, 480)
        self.resize(860, 540)
        self.setModal(True)

        self.setup_ui()
        self.apply_theme(theme)

    def setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("SAVED DATABASE ACCOUNTS")
        title.setObjectName("db_title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Each card shows the profile name, database type, and connection target. "
            "Select a card and click SWITCH, or double-click it."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("db_info")
        layout.addWidget(subtitle)

        self.empty_label = QLabel(
            "No saved accounts yet. Click ADD ACCOUNT to save your first connection."
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setObjectName("db_info")
        layout.addWidget(self.empty_label)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("account_list")
        self.list_widget.setSpacing(8)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.currentRowChanged.connect(
            self.update_account_card_selection
        )
        self.refresh_list()
        layout.addWidget(self.list_widget, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.switch_button = QPushButton("SWITCH ACCOUNT")
        self.add_button = QPushButton("ADD ACCOUNT")
        self.remove_button = QPushButton("REMOVE")
        self.cancel_button = QPushButton("CANCEL")

        for button in (
            self.switch_button,
            self.add_button,
            self.remove_button,
            self.cancel_button,
        ):
            button.setObjectName("header_button")
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        buttons.addWidget(self.switch_button)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.switch_button.clicked.connect(self.switch_account)
        self.add_button.clicked.connect(self.add_account)
        self.remove_button.clicked.connect(self.remove_account)
        self.cancel_button.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(
            lambda _item: self.switch_account()
        )

    def _is_active_profile(self, profile, active_profile):
        return (
            active_profile is not None
            and active_profile.keyring_service == profile.keyring_service
        )

    def refresh_list(self):

        self.list_widget.clear()
        self.account_cards = []
        self.empty_label.setVisible(not bool(self.profiles))
        active_profile = getattr(self.parent(), "current_profile", None)
        active_row = None

        for row, profile in enumerate(self.profiles):
            is_active = self._is_active_profile(profile, active_profile)
            if is_active:
                active_row = row

            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 78))
            self.list_widget.addItem(item)

            card = AccountCardWidget(profile, is_active, self.theme)
            self.list_widget.setItemWidget(item, card)
            self.account_cards.append(card)

        if self.profiles:
            # Default to the live connection so the selected account is clear.
            self.list_widget.setCurrentRow(active_row if active_row is not None else 0)
        else:
            self.list_widget.setCurrentRow(-1)

        self.update_account_card_selection()

    def update_account_card_selection(self, *_args):
        for row, card in enumerate(self.account_cards):
            card.set_visual_state(self.theme, selected=(row == self.list_widget.currentRow()))

    def selected(self):

        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.profiles):
            return None
        return self.profiles[row]

    def switch_account(self):

        profile = self.selected()
        if profile is None:
            QMessageBox.warning(
                self,
                "Select an Account",
                "Select a saved account first.",
            )
            return

        self.selected_profile = profile
        self.accept()

    def add_account(self):

        dialog = DatabaseLoginDialog(
            self.theme,
            self,
            new_profile=True,
            force_remember=True,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.added_profile = dialog.profile
        self.added_password = dialog.password
        self.selected_profile = dialog.profile
        self.accept()

    def remove_account(self):

        profile = self.selected()
        if profile is None:
            return

        answer = QMessageBox.question(
            self,
            "Remove Account",
            f"Remove saved account '{profile.profile_name}'?\n\n"
            "This also removes its saved password from the credential store.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        _remove_saved_profile(profile)
        row = self.list_widget.currentRow()
        self.profiles = _saved_profiles()
        self.refresh_list()

        if self.list_widget.count():
            self.list_widget.setCurrentRow(
                min(max(row, 0), self.list_widget.count() - 1)
            )

    def apply_theme(self, theme):

        self.theme = theme
        list_style = f"""
            QListWidget#account_list {{
                background-color: {theme['bg']};
                color: {theme['ink']};
                border: 1px solid {theme['line']};
                border-radius: {max(6, int(theme['radius']))}px;
                padding: 8px; outline: 0;
            }}
            QListWidget#account_list::item {{
                background: transparent; border: none;
                padding: 0; margin: 0;
            }}
            QListWidget#account_list::item:selected {{
                background: transparent; border: none;
            }}
        """
        self.setStyleSheet(
            build_stylesheet(theme, chevron_path(theme["ink"])) + list_style
        )
        self.update_account_card_selection()


# ============================================================
# SQL*PLUS PANEL
# ============================================================

# ============================================================
# SQL*PLUS PANEL
# ============================================================

class SQLPlusPanel(QFrame):

    sql_completed = Signal(str)

    CONNECTED_RE = re.compile(r"(?<!dis)connected( to|\.)")

    def __init__(self):
        super().__init__()

        self.setObjectName("sqlplus_panel")
        self.process = QProcess(self)
        self.profile = None
        self.password = ""
        self.adapter = None
        self.current_statement = ""
        self.history = []
        self.history_index = 0

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.started.connect(self.sqlplus_started)
        self.process.errorOccurred.connect(self.sqlplus_error)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.title_label = QLabel("SQL*PLUS")
        self.title_label.setObjectName("panel_title")

        self.connection_label = QLabel()
        self.connection_label.setObjectName("connection")
        self.set_connection("● NOT CONNECTED", "wait")

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.connection_label)
        layout.addLayout(header)

        self.output = QPlainTextEdit()
        self.output.setObjectName("sql_console")
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.output_highlighter = ConsoleHighlighter(self.output.document())
        layout.addWidget(self.output, 1)

        self.input = SQLInput()
        self.input.submitted.connect(self.send_sql_line)
        self.input.history_up.connect(self.show_previous)
        self.input.history_down.connect(self.show_next)
        layout.addWidget(self.input)

    def set_connection(self, text, state):
        self.connection_label.setText(text)
        self.connection_label.setProperty("state", state)
        repolish(self.connection_label)

    def connect_profile(self, profile, password):
        self.disconnect_profile(clear_output=False)
        self.profile = profile
        self.password = password
        self.current_statement = ""

        if profile.database_type == "oracle":
            self.title_label.setText("SQL*PLUS")
            sqlplus_path = resolve_sqlplus_path()

            # Some Oracle installations use a custom directory. If automatic
            # discovery fails, let the user choose sqlplus.exe once and save
            # only the executable path in QSettings (never database passwords).
            if not sqlplus_path:
                selected_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Locate Oracle SQL*Plus",
                    str(Path.home()),
                    "SQL*Plus executable (sqlplus.exe);;Executable files (*.exe)",
                )
                if selected_path and Path(selected_path).is_file():
                    selected_file = Path(selected_path)
                    if selected_file.name.casefold() == "sqlplus.exe":
                        sqlplus_path = str(selected_file.resolve())
                        APP_SETTINGS.setValue("sqlplus_path", sqlplus_path)
                        APP_SETTINGS.sync()

            if not sqlplus_path:
                self.set_connection("● SQL*PLUS PATH MISSING", "bad")
                self.append_output(
                    "\n[QRYVANTA ERROR] Could not locate sqlplus.exe.\n"
                    "Install Oracle Client/SQL*Plus, then reconnect and select sqlplus.exe "
                    "when prompted. QRYVANTA will remember the path.\n"
                )
                return

            APP_SETTINGS.setValue("sqlplus_path", sqlplus_path)
            APP_SETTINGS.sync()
            self.set_connection("● CONNECTING", "wait")
            # SQL*Plus may need DLLs located beside its executable, so use its
            # installation directory as the process working directory.
            self.process.setWorkingDirectory(str(Path(sqlplus_path).parent))
            self.process.start(sqlplus_path, ["/nolog"])
            return

        self.title_label.setText("SQL CONSOLE")
        try:
            self.adapter = create_adapter(
                profile.database_type,
                profile=profile,
                password=password,
            )
            connection = self.adapter.connect()
            connection.close()
            self.set_connection(
                f"● {self.adapter.name.upper()} • {profile.username}",
                "ok",
            )
            self.append_output(
                f"\n[QRYVANTA] Connected to {profile.database_type.upper()} "
                f"database '{profile.database}'.\n"
            )
        except Exception as error:
            self.adapter = None
            self.set_connection("● DATABASE ERROR", "bad")
            self.append_output(f"\n[DATABASE ERROR] {error}\n")

    def sqlplus_started(self):
        if self.profile is None or self.profile.database_type != "oracle":
            return
        connect_command = (
            "connect "
            f"{self.profile.username}/"
            f"{self.password}@"
            f"{self.profile.host}:"
            f"{self.profile.port}/"
            f"{self.profile.database}\n"
        )
        self.process.write(connect_command.encode())

    def disconnect_profile(self, clear_output=True):
        if self.process.state() != QProcess.NotRunning:
            try:
                self.process.write(b"disconnect\n")
                self.process.waitForBytesWritten(300)
            except Exception:
                pass
            self.process.terminate()
            if not self.process.waitForFinished(800):
                self.process.kill()
                self.process.waitForFinished(300)

        self.profile = None
        self.password = ""
        self.adapter = None
        self.current_statement = ""
        self.title_label.setText("SQL*PLUS")
        self.set_connection("● NOT CONNECTED", "wait")
        if clear_output:
            self.output.clear()

    def read_output(self):
        data = (
            self.process.readAllStandardOutput().data().decode(
                "utf-8", errors="replace"
            )
        )
        if not data:
            return
        self.append_output(data)
        if self.CONNECTED_RE.search(data.lower()):
            user = self.profile.username if self.profile else "USER"
            self.set_connection(f"● ORACLE • {user}", "ok")

    def read_error(self):
        data = (
            self.process.readAllStandardError().data().decode(
                "utf-8", errors="replace"
            )
        )
        if data:
            self.append_output(data)

    def sqlplus_error(self, error):
        self.set_connection("● SQL*PLUS ERROR", "bad")
        self.append_output(f"\n[SQL*PLUS ERROR] {error}\n")

    def append_output(self, text):
        self.output.appendPlainText(text)
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _render_native_result(self, result):
        if result.columns:
            if result.rows:
                header = " | ".join(result.columns)
                separator = "-+-".join("-" * max(3, len(col)) for col in result.columns)
                self.append_output("\n" + header + "\n" + separator + "\n")
                for row in result.rows:
                    self.append_output(" | ".join("" if value is None else str(value) for value in row) + "\n")
                self.append_output(f"\n{len(result.rows)} row(s) selected.\n")
            else:
                self.append_output("\n0 rows selected.\n")
        else:
            affected = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else 0
            self.append_output(f"\n{affected} row(s) affected.\n")
            if result.message:
                self.append_output(result.message + "\n")

    def send_sql_line(self, text):
        text = text.rstrip()
        if not text:
            return
        if self.profile is None:
            self.append_output("\n[QRYVANTA] Please LOGIN first.\n")
            return

        self.append_output(f"\nSQL> {text}\n")
        self.current_statement += ("\n" if self.current_statement else "") + text

        if not statement_complete(self.current_statement):
            return

        sql = self.current_statement.strip()
        self.current_statement = ""

        if not is_sql_statement(sql):
            if self.profile.database_type == "oracle" and self.process.state() != QProcess.NotRunning:
                self.process.write((text + "\n").encode())
            else:
                self.append_output("[QRYVANTA] Statement captured but not analyzed.\n")
            return

        if self.history[-1:] != [sql]:
            self.history.append(sql)
        self.history_index = len(self.history)

        if self.profile.database_type == "oracle":
            if self.process.state() != QProcess.NotRunning:
                self.process.write((sql + "\n").encode())
            self.sql_completed.emit(sql)
            return

        try:
            if self.adapter is None:
                self.adapter = create_adapter(
                    self.profile.database_type,
                    profile=self.profile,
                    password=self.password,
                )
            result = self.adapter.execute(sql)
            self._render_native_result(result)
            self.sql_completed.emit(sql)
        except Exception as error:
            self.set_connection("● EXECUTION ERROR", "bad")
            self.append_output(f"\n[DATABASE ERROR] {error}\n")

    def show_previous(self):
        if not self.history:
            return
        self.history_index = max(0, self.history_index - 1)
        self.input.setPlainText(self.history[self.history_index])
        self.input.moveCursor(QTextCursor.MoveOperation.End)

    def show_next(self):
        if not self.history:
            return
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = len(self.history)
            self.input.clear()
            return
        self.input.setPlainText(self.history[self.history_index])
        self.input.moveCursor(QTextCursor.MoveOperation.End)

    def apply_theme(self, theme):
        self.output_highlighter.set_colors(theme["syn_console"])
        self.input.apply_theme(theme)

# ============================================================
# ANALYSIS PANEL
# ============================================================

class AnalysisPanel(QFrame):

    download_requested = Signal(str)

    def __init__(self):

        super().__init__()

        self.setObjectName("analysis_panel")

        self.cards = {}

        self.setup_ui()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def build_card(self, name, title):

        frame = QFrame()

        frame.setObjectName(name)

        layout = QVBoxLayout(frame)

        layout.setContentsMargins(16, 14, 16, 16)

        layout.setSpacing(10)

        label = QLabel(title)

        label.setObjectName("card_title")

        layout.addWidget(label)

        self.cards[name] = frame

        return frame, layout

    @staticmethod
    def build_text(layout, max_height=None):

        box = QPlainTextEdit()

        box.setReadOnly(True)

        box.setObjectName("analysis_text")

        if max_height:
            box.setMaximumHeight(max_height)

        layout.addWidget(box)

        return box

    def setup_ui(self):

        # Keep the existing card design, but allow the analyzer panel
        # to scroll vertically when the window is not tall enough to
        # display every card at once. This prevents lower content from
        # being clipped while keeping the visual design unchanged.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.analysis_scroll = QScrollArea()
        self.analysis_scroll.setFrameShape(QFrame.NoFrame)
        self.analysis_scroll.setWidgetResizable(True)
        self.analysis_scroll.setObjectName("analysis_scroll")

        self.analysis_content = QWidget()
        self.analysis_content.setObjectName("analysis_content")

        self.analysis_content_layout = QVBoxLayout(
            self.analysis_content
        )
        self.analysis_content_layout.setContentsMargins(18, 18, 18, 18)
        self.analysis_content_layout.setSpacing(14)

        self.analysis_scroll.setWidget(self.analysis_content)
        outer_layout.addWidget(self.analysis_scroll)

        layout = self.analysis_content_layout

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = QHBoxLayout()

        title = QLabel("QRYVANTA")

        title.setObjectName("sqlens_logo")

        subtitle = QLabel("QUERY INTELLIGENCE STUDIO")

        subtitle.setObjectName("subtitle")

        self.live_label = QLabel("● REAL-TIME")

        self.live_label.setObjectName("live")

        header.addWidget(title)

        header.addSpacing(10)

        header.addWidget(subtitle)

        header.addStretch()

        self.download_button = QPushButton("DOWNLOAD ▾")
        self.download_button.setObjectName("header_button")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_menu = QMenu(self)
        for label, key in (
            ("Database Table CSV", "database_csv"),
            ("SQL Command History (TXT)", "history_txt"),
            ("Processing Report (PDF)", "report_pdf"),
            ("Processing Report (DOCX)", "report_docx"),
            ("Processing Report (TXT)", "report_txt"),
        ):
            action = self.download_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, chosen=key: self.download_requested.emit(chosen))
        self.download_button.setMenu(self.download_menu)
        header.addWidget(self.download_button)
        header.addWidget(self.live_label)

        layout.addLayout(header)

        # ----------------------------------------------------
        # Last Query
        # ----------------------------------------------------

        query_card, query_layout = self.build_card(
            "query_card",
            "LAST SQL*PLUS QUERY",
        )

        self.query_box = self.build_text(query_layout, max_height=96)

        layout.addWidget(query_card)

        # ----------------------------------------------------
        # Health + Complexity
        # ----------------------------------------------------

        upper = QHBoxLayout()

        upper.setSpacing(14)

        score_card, score_layout = self.build_card(
            "score_card",
            "QUERY HEALTH",
        )

        self.score_label = QLabel("—")

        self.score_label.setAlignment(Qt.AlignCenter)

        self.score_label.setObjectName("score")

        score_layout.addWidget(self.score_label, 1)

        suffix = QLabel("/ 100")

        suffix.setObjectName("score_suffix")

        suffix.setAlignment(Qt.AlignCenter)

        score_layout.addWidget(suffix)

        upper.addWidget(score_card, 1)

        complexity_card, complexity_layout = self.build_card(
            "complexity_card",
            "QUERY COMPLEXITY",
        )

        self.complexity_box = QLabel("No analysis yet.")

        self.complexity_box.setObjectName("complexity")
        self.complexity_box.setTextFormat(Qt.PlainText)
        self.complexity_box.setWordWrap(False)
        self.complexity_box.setMinimumHeight(118)
        self.complexity_box.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        complexity_layout.addWidget(self.complexity_box)

        complexity_layout.addStretch()

        upper.addWidget(complexity_card, 1)

        layout.addLayout(upper)

        # ----------------------------------------------------
        # Findings
        # ----------------------------------------------------

        findings_row = QHBoxLayout()

        findings_row.setSpacing(14)

        lint_card, lint_layout = self.build_card(
            "lint_card",
            "LINT WARNINGS",
        )

        self.lint_box = self.build_text(lint_layout)

        findings_row.addWidget(lint_card, 1)

        performance_card, performance_layout = self.build_card(
            "performance_card",
            "PERFORMANCE FINDINGS",
        )

        self.performance_box = self.build_text(performance_layout)

        findings_row.addWidget(performance_card, 1)

        layout.addLayout(findings_row, 2)

        # ----------------------------------------------------
        # Recommendations
        # ----------------------------------------------------

        recommendation_card, recommendation_layout = self.build_card(
            "recommendation_card",
            "INDEX RECOMMENDATIONS",
        )

        self.recommendations_box = self.build_text(recommendation_layout)

        layout.addWidget(recommendation_card, 1)

        # ----------------------------------------------------
        # Highlighters
        # ----------------------------------------------------

        self.query_highlighter = SQLHighlighter(self.query_box.document())

        self.findings_highlighters = [
            FindingsHighlighter(box.document())
            for box in (
                self.lint_box,
                self.performance_box,
                self.recommendations_box,
            )
        ]

    # --------------------------------------------------------
    # THEME
    # --------------------------------------------------------

    def apply_theme(self, theme):

        colors = theme["syn_well"]

        self.query_highlighter.set_colors(colors)

        for highlighter in self.findings_highlighters:
            highlighter.set_colors(colors)

        shadow = theme["shadow"]

        for name, frame in self.cards.items():

            if not shadow:
                frame.setGraphicsEffect(None)
                continue

            effect = QGraphicsDropShadowEffect(frame)

            effect.setOffset(shadow["dx"], shadow["dy"])

            effect.setBlurRadius(shadow["blur"])

            color = QColor(
                theme["cards"][name]["edge"]
                if shadow["use_edge"]
                else shadow["color"]
            )

            color.setAlpha(shadow["alpha"])

            effect.setColor(color)

            frame.setGraphicsEffect(effect)

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    def show_analysis(
        self,
        sql,
        analysis,
        lint_findings,
    ):

        self.query_box.setPlainText(sql)

        score = analysis.get(
            "query_score",
            0,
        )

        self.score_label.setText(str(score))

        # Complexity

        info = analysis.get(
            "query_info",
            {},
        )

        def yes_no(value):
            return "yes" if value else "no"

        rows = [
            ("Tables", info.get("table_count", 0)),
            ("JOINs", info.get("join_count", 0)),
            ("Selected columns", info.get("selected_column_count", 0)),
            ("Filters", info.get("filter_count", 0)),
            ("GROUP BY", yes_no(info.get("has_group_by", False))),
            ("ORDER BY", yes_no(info.get("has_order_by", False))),
            ("DISTINCT", yes_no(info.get("has_distinct", False))),
            ("Aggregates", info.get("aggregate_count", 0)),
        ]

        self.complexity_box.setText(
            "\n".join(f"{label:<18}{value}" for label, value in rows)
        )

        # Lint

        lint_lines = []

        for finding in lint_findings:

            lint_lines.append(
                f"{finding.get('rule_id', '')} "
                f"[{finding.get('severity', '')}]"
            )

            lint_lines.append(
                finding.get(
                    "message",
                    finding.get(
                        "problem",
                        "",
                    ),
                )
            )

            explanation = finding.get(
                "explanation",
                "",
            )

            if explanation:
                lint_lines.append(explanation)

            lint_lines.append("")

        self.lint_box.setPlainText(
            "\n".join(lint_lines)
            if lint_lines
            else "✓ No lint issues."
        )

        # Performance

        performance_findings = analysis.get(
            "findings",
            [],
        )

        performance_lines = []

        for finding in performance_findings:

            rule_id = finding.get(
                "rule_id",
                "",
            )

            if not rule_id.startswith("P"):
                continue

            performance_lines.append(
                f"{rule_id} "
                f"[{finding.get('severity', '')}]"
            )

            performance_lines.append(
                finding.get(
                    "message",
                    finding.get(
                        "problem",
                        "",
                    ),
                )
            )

            explanation = finding.get(
                "explanation",
                "",
            )

            if explanation:
                performance_lines.append(explanation)

            performance_lines.append("")

        self.performance_box.setPlainText(
            "\n".join(performance_lines)
            if performance_lines
            else "✓ No performance issues."
        )

        # Recommendations

        recommendations = analysis.get(
            "recommendations",
            [],
        )

        rec_lines = []

        for recommendation in recommendations:

            rec_lines.append(f"TYPE: {recommendation.get('type', '')}")

            rec_lines.append(recommendation.get("message", ""))

            sql_text = recommendation.get(
                "sql",
                "",
            )

            if sql_text:
                rec_lines.append(f"SQL: {sql_text}")

            rec_lines.append("")

        self.recommendations_box.setPlainText(
            "\n".join(rec_lines)
            if rec_lines
            else "✓ No additional recommendations."
        )


# ============================================================
# MAIN WINDOW
# ============================================================

class QRYVANTAWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        # Restore the user's last selected theme across application restarts.
        # Fall back safely if settings contain an invalid/obsolete theme name.
        saved_theme = APP_SETTINGS.value(
            "current_theme",
            "01 · NEO-BRUTALISM",
            type=str,
        )
        self.current_theme = (
            saved_theme
            if saved_theme in THEMES
            else "01 · NEO-BRUTALISM"
        )

        self.current_profile = None
        self.current_password = ""
        self.current_adapter = None
        self.is_night_mode = APP_SETTINGS.value("night_mode", False, type=bool)
        self.latest_report = {"status": "No analysis has been run", "query": "", "analysis": None, "lint_findings": [], "database_type": None}

        self.setWindowTitle(
            "QRYVANTA — Query Intelligence Studio"
        )

        self.resize(1600, 900)
        self.setMinimumSize(1100, 700)

        self.setup_ui()

        self.theme_selector.currentTextChanged.connect(
            self.set_theme
        )

        # Store the current value as well so the setting is initialized
        # on first launch and remains available across upgrades.
        APP_SETTINGS.setValue(
            "current_theme",
            self.current_theme,
        )
        APP_SETTINGS.sync()

        self.apply_theme()

        # Do not block construction with a modal dialog.
        QTimer.singleShot(
            0,
            self.initialize_connection
        )

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def make_header_button(self, text, handler):

        button = QPushButton(text)
        button.setObjectName("header_button")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(handler)

        return button

    def setup_ui(self):

        central = QWidget()
        central.setObjectName("central")

        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()
        header.setSpacing(8)

        logo = QLabel("QRYVANTA")
        logo.setObjectName("main_logo")

        tagline = QLabel(
            "QUERY INTELLIGENCE STUDIO"
        )
        tagline.setObjectName("tagline")

        header.addWidget(logo)
        header.addSpacing(10)
        header.addWidget(tagline)
        header.addStretch()

        self.analyzer_button = self.make_header_button(
            "ANALYZER",
            self.show_analyzer,
        )

        self.database_button = self.make_header_button(
            "DATABASE",
            self.show_database,
        )

        self.side_button = self.make_header_button(
            "S|S",
            self.side_by_side,
        )

        self.stacked_button = self.make_header_button(
            "S↕S",
            self.stacked,
        )

        self.account_status = QLabel(
            "● NOT CONNECTED"
        )
        self.account_status.setObjectName(
            "account_status"
        )
        self.set_account_status(
            "● NOT CONNECTED",
            "wait",
        )

        self.login_button = self.make_header_button(
            "LOGIN",
            self.login,
        )

        self.switch_button = self.make_header_button(
            "SWITCH ACCOUNT",
            self.switch_account,
        )

        self.logout_button = self.make_header_button(
            "LOGOUT",
            self.logout,
        )

        self.help_menu_button = self.make_header_button("? ▾", self.show_help_menu)
        self.help_menu = QMenu(self)
        for label, handler in (
            ("LEARN", self.show_learn),
            ("HELP", self.show_help),
            ("QUIZ", self.show_quiz),
            ("COMPETITIVE EXAM", self.show_competitive_exam),
            ("DEVELOPED BY", self.show_developed_by),
        ):
            self.help_menu.addAction(label, handler)

        self.day_night_button = self.make_header_button("☾ NIGHT", self.toggle_day_night)
        theme_label = QLabel("THEME")
        theme_label.setObjectName("theme_label")

        self.theme_selector = QComboBox()
        self.theme_selector.setObjectName(
            "theme_selector"
        )
        self.theme_selector.setCursor(
            Qt.PointingHandCursor
        )
        self.theme_selector.addItems(
            list(THEMES.keys())
        )
        self.theme_selector.setCurrentText(
            self.current_theme
        )

        header.addWidget(self.analyzer_button)
        header.addWidget(self.database_button)
        header.addWidget(self.side_button)
        header.addWidget(self.stacked_button)

        header.addSpacing(8)

        header.addWidget(
            self.account_status
        )

        header.addWidget(
            self.login_button
        )

        header.addWidget(
            self.switch_button
        )

        header.addWidget(
            self.logout_button
        )
        header.addWidget(self.help_menu_button)
        header.addWidget(self.day_night_button)

        header.addSpacing(10)
        header.addWidget(theme_label)
        header.addWidget(self.theme_selector)

        main_layout.addLayout(header)

        # The current default layout is side-by-side, so the
        # button for the current layout is hidden.
        self.side_button.hide()
        self.stacked_button.show()

        # ====================================================
        # MAIN CONTENT
        # ====================================================

        self.main_splitter = QSplitter(
            Qt.Horizontal
        )
        self.main_splitter.setHandleWidth(10)

        self.sqlplus_panel = SQLPlusPanel()

        self.main_splitter.addWidget(
            self.sqlplus_panel
        )

        self.right_stack = QStackedWidget()

        self.analysis_panel = AnalysisPanel()

        self.database_view = DatabaseView()

        self.right_stack.addWidget(
            self.analysis_panel
        )

        self.right_stack.addWidget(
            self.database_view
        )

        self.main_splitter.addWidget(
            self.right_stack
        )

        self.main_splitter.setSizes(
            [800, 800]
        )

        main_layout.addWidget(
            self.main_splitter,
            1,
        )

        # ====================================================
        # STATUS
        # ====================================================

        self.status_label = QLabel(
            "● QRYVANTA READY"
        )
        self.status_label.setObjectName(
            "status"
        )

        main_layout.addWidget(
            self.status_label
        )

        # ====================================================
        # SIGNALS
        # ====================================================

        self.sqlplus_panel.sql_completed.connect(
            self.analyze_query
        )
        self.analysis_panel.download_requested.connect(self.handle_download_action)

        self.update_account_buttons()

    # --------------------------------------------------------
    # ACCOUNT STATE
    # --------------------------------------------------------

    def set_account_status(
        self,
        text,
        state,
    ):

        self.account_status.setText(text)
        self.account_status.setProperty(
            "state",
            state,
        )

        repolish(
            self.account_status
        )

    def update_account_buttons(self):

        has_active = (
            self.current_profile
            is not None
        )

        # Keep the top bar clean: only the action that makes sense
        # for the current session is shown.
        self.login_button.setVisible(
            not has_active
        )

        self.logout_button.setVisible(
            has_active
        )

        self.switch_button.setVisible(
            has_active
        )

        self.login_button.setEnabled(
            not has_active
        )

        self.logout_button.setEnabled(
            has_active
        )

        self.switch_button.setEnabled(
            has_active
        )

    def _store_last_profile(
        self,
        profile,
    ):

        APP_SETTINGS.setValue(
            "last_profile",
            profile.keyring_service,
        )
        APP_SETTINGS.sync()

    def _clear_last_profile(self):

        APP_SETTINGS.remove(
            "last_profile"
        )
        APP_SETTINGS.sync()

    def initialize_connection(self):

        last_key = APP_SETTINGS.value(
            "last_profile",
            "",
        )

        profiles = _saved_profiles()

        restored = None

        if last_key:

            for profile in profiles:

                if _profile_key(profile) == last_key:

                    password = get_saved_password(
                        profile
                    )

                    if password:

                        try:
                            connect_active_profile(
                                profile,
                                password,
                                remember=True,
                            )

                            restored = (
                                profile,
                                password,
                            )

                        except Exception:
                            restored = None

                    break

        if restored:

            self.activate_profile(
                restored[0],
                restored[1],
                show_message=False,
            )

            return

        self.set_account_status(
            "● LOGIN REQUIRED",
            "wait",
        )

        self.update_account_buttons()

        self.login()

    def activate_profile(
        self,
        profile,
        password,
        show_message=True,
    ):

        self.current_profile = profile
        self.current_password = password
        self.current_adapter = create_adapter(
            profile.database_type,
            profile=profile,
            password=password,
        )

        self.sqlplus_panel.connect_profile(
            profile,
            password,
        )

        self.database_view.set_profile(
            profile,
            password,
        )

        self._store_last_profile(profile)

        display_name = (
            f"● {profile.database_type.upper()} • "
            f"{profile.username}@{profile.host}"
        )

        self.set_account_status(display_name, "ok")
        self.update_account_buttons()
        self.status_label.setText(
            f"● CONNECTED • {profile.profile_name}"
        )

        if show_message:
            QMessageBox.information(
                self,
                "QRYVANTA",
                f"Connected to:\n\n{profile.profile_name}",
            )

    # --------------------------------------------------------
    # LOGIN / LOGOUT / SWITCH
    # --------------------------------------------------------

    def login(self):

        dialog = DatabaseLoginDialog(
            self.active_theme(),
            self,
            self.current_profile,
        )

        result = dialog.exec()

        if result != QDialog.Accepted:

            if self.current_profile is None:

                self.set_account_status(
                    "● LOGIN REQUIRED",
                    "wait",
                )

                self.status_label.setText(
                    "● QRYVANTA WAITING FOR LOGIN"
                )

            return

        try:

            connect_active_profile(
                dialog.profile,
                dialog.password,
                remember=dialog.remember_check.isChecked(),
            )

            if dialog.remember_check.isChecked():
                _upsert_saved_profile(
                    dialog.profile
                )

            self.activate_profile(
                dialog.profile,
                dialog.password,
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Connection Failed",
                str(error),
            )

    def switch_account(self):

        profiles = _saved_profiles()

        # Show the account manager even when there are no saved profiles,
        # so the user can create one through ADD ACCOUNT.
        dialog = AccountSwitcherDialog(
            self.active_theme(),
            profiles,
            self,
        )

        result = dialog.exec()

        if result != QDialog.Accepted:

            return

        # ADD ACCOUNT returns the newly verified and saved profile. Make it
        # the active account immediately instead of reopening the saved list.
        if dialog.added_profile is not None:
            selected = dialog.added_profile
            password = dialog.added_password
            try:
                connect_active_profile(
                    selected,
                    password,
                    remember=True,
                )
                self.activate_profile(selected, password)
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "Connection Failed",
                    str(error),
                )
            return

        selected = dialog.selected_profile

        if selected is None:
            return

        password = get_saved_password(selected)

        if not password:

            login_dialog = DatabaseLoginDialog(
                self.active_theme(),
                self,
                selected,
            )

            if login_dialog.exec() != QDialog.Accepted:
                return

            selected = login_dialog.profile
            password = login_dialog.password

            connect_active_profile(
                selected,
                password,
                remember=login_dialog.remember_check.isChecked(),
            )

            if login_dialog.remember_check.isChecked():
                _upsert_saved_profile(
                    selected
                )

        else:

            connect_active_profile(
                selected,
                password,
                remember=True,
            )

        self.activate_profile(
            selected,
            password,
        )

    def logout(self):

        if self.current_profile is None:
            return

        profile_name = (
            self.current_profile.profile_name
        )

        answer = QMessageBox.question(
            self,
            "Logout",
            f"Logout from '{profile_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if answer != QMessageBox.Yes:
            return

        self.sqlplus_panel.disconnect_profile()

        clear_active_profile()

        self.current_profile = None
        self.current_password = ""
        self.current_adapter = None
        self.database_view.clear_profile()

        self._clear_last_profile()

        self.set_account_status(
            "● LOGGED OUT",
            "wait",
        )

        self.status_label.setText(
            "● QRYVANTA LOGGED OUT"
        )

        self.update_account_buttons()

        # After logout, immediately present the login window again.
        QTimer.singleShot(0, self.login)

    # --------------------------------------------------------
    # ANALYZER
    # --------------------------------------------------------

    def analyze_query(
        self,
        query,
    ):

        query = query.strip()
        if not query or not is_sql_statement(query):
            return

        if self.current_profile is None or self.current_adapter is None:
            self.status_label.setText("● LOGIN REQUIRED")
            return

        self.status_label.setText("● ANALYZING QUERY")
        QApplication.processEvents()

        try:
            dialect = self.current_adapter.dialect
            tree = sqlglot.parse_one(query, read=dialect)
            lint_findings = run_linter(tree, dialect=dialect)
            analysis = analyze_query(
                query,
                tree,
                lint_findings,
                database_type=self.current_profile.database_type,
                adapter=self.current_adapter,
            )
            self.latest_report = {
                "status": "Analysis complete",
                "query": query,
                "analysis": analysis,
                "lint_findings": list(lint_findings or []),
                "database_type": self.current_profile.database_type,
            }

            self.analysis_panel.show_analysis(
                query,
                analysis,
                lint_findings,
            )
            self.right_stack.setCurrentWidget(self.analysis_panel)
            self.refresh_active_buttons()
            self.status_label.setText(
                "● ANALYSIS COMPLETE"
            )

        except Exception as error:
            self.latest_report = {
                "status": "Analysis failed",
                "query": query,
                "analysis": None,
                "lint_findings": [],
                "database_type": getattr(self.current_profile, "database_type", None),
                "error": str(error),
            }
            self.right_stack.setCurrentWidget(self.analysis_panel)
            self.refresh_active_buttons()
            self.status_label.setText("● ANALYSIS FAILED")
            self.analysis_panel.query_box.setPlainText(query)
            self.analysis_panel.performance_box.setPlainText(
                "ANALYSIS ERROR\n\n" + str(error)
            )

    # --------------------------------------------------------
    # VIEW SWITCHING
    # --------------------------------------------------------

    def refresh_active_buttons(self):
        """Highlight the header button of the view currently shown."""

        current = self.right_stack.currentWidget()

        for view, button in (
            (
                self.analysis_panel,
                self.analyzer_button,
            ),
            (
                self.database_view,
                self.database_button,
            ),
        ):

            button.setProperty(
                "active",
                "true"
                if view is current
                else "false",
            )

            repolish(button)

    def show_analyzer(self):

        # Analyzer is the normal analysis view. Do not hide the SQL
        # console here; that was the old FULL ANALYZER behaviour.
        self.sqlplus_panel.show()
        self.right_stack.setCurrentWidget(
            self.analysis_panel
        )

        self.refresh_active_buttons()

    def show_database(self):

        self.right_stack.setCurrentWidget(
            self.database_view
        )

        self.refresh_active_buttons()

        try:
            self.database_view.load_tables()
        except Exception:
            pass

    # --------------------------------------------------------
    # LAYOUT
    # --------------------------------------------------------

    def side_by_side(self):

        self.sqlplus_panel.show()

        self.main_splitter.setOrientation(
            Qt.Horizontal
        )

        self.main_splitter.setSizes(
            [800, 800]
        )

        # Current layout = side-by-side.
        self.side_button.hide()
        self.stacked_button.show()

    def stacked(self):

        self.sqlplus_panel.show()

        self.main_splitter.setOrientation(
            Qt.Vertical
        )

        self.main_splitter.setSizes(
            [420, 480]
        )

        # Current layout = stacked.
        self.stacked_button.hide()
        self.side_button.show()

    def full_analyzer(self):

        self.sqlplus_panel.hide()

    # --------------------------------------------------------
    # THEME
    # --------------------------------------------------------

    def set_theme(
        self,
        theme_name,
    ):

        if theme_name not in THEMES:
            return

        self.current_theme = theme_name

        # Persist the selection using QSettings (outside the app bundle).
        APP_SETTINGS.setValue(
            "current_theme",
            theme_name,
        )
        APP_SETTINGS.sync()

        self.apply_theme()

    def active_theme(self):
        return theme_variant(THEMES[self.current_theme], self.is_night_mode)

    def toggle_day_night(self):
        self.is_night_mode = not self.is_night_mode
        APP_SETTINGS.setValue("night_mode", self.is_night_mode)
        APP_SETTINGS.sync()
        self.apply_theme()

    def show_help_menu(self):
        self.help_menu.popup(self.help_menu_button.mapToGlobal(self.help_menu_button.rect().bottomLeft()))

    def _open_feature(self, dialog_type):
        dialog_type(self.active_theme(), self).exec()

    def show_learn(self):
        self._open_feature(LearnDialog)

    def show_help(self):
        self._open_feature(HelpDialog)

    def show_quiz(self):
        self._open_feature(QuizDialog)

    def show_competitive_exam(self):
        self._open_feature(CompetitiveExamDialog)

    def show_developed_by(self):
        self._open_feature(DeveloperDialog)

    def handle_download_action(self, action):
        try:
            if action == "database_csv":
                widget = self.database_view.data_table
                columns = widget.columnCount()
                if columns <= 0:
                    QMessageBox.information(self, "Database CSV", "No table is currently loaded in Database Explorer.")
                    return
                headers = []
                for col in range(columns):
                    item = widget.horizontalHeaderItem(col)
                    headers.append(item.text() if item else f"Column {col + 1}")
                rows = []
                for row in range(widget.rowCount()):
                    rows.append([widget.item(row, col).text() if widget.item(row, col) else "" for col in range(columns)])
                default_name = (self.database_view.selected_table_label.text().strip().replace(" ", "_") or "database_table") + ".csv"
                path, _ = QFileDialog.getSaveFileName(self, "Export Database Explorer table", default_name, "CSV files (*.csv)")
                if not path:
                    return
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                export_table_csv(path, headers, rows)
                QMessageBox.information(self, "Export complete", f"Exported {len(rows)} rows and {len(headers)} columns.\n{path}")
            elif action == "history_txt":
                path, _ = QFileDialog.getSaveFileName(self, "Export SQL command history", "QRYVANTA_SQL_History.txt", "Text files (*.txt)")
                if not path:
                    return
                if not path.lower().endswith(".txt"):
                    path += ".txt"
                from pathlib import Path as _Path
                _Path(path).write_text(format_command_history(self.sqlplus_panel.history), encoding="utf-8")
                QMessageBox.information(self, "Export complete", f"Command history saved.\n{path}")
            elif action in {"report_pdf", "report_docx", "report_txt"}:
                ext = {"report_pdf": "pdf", "report_docx": "docx", "report_txt": "txt"}[action]
                default_name = f"QRYVANTA_Processing_Report.{ext}"
                filters = {"pdf": "PDF files (*.pdf)", "docx": "Word documents (*.docx)", "txt": "Text files (*.txt)"}
                path, _ = QFileDialog.getSaveFileName(self, "Export processing report", default_name, filters[ext])
                if not path:
                    return
                if not path.lower().endswith("." + ext):
                    path += "." + ext
                exporter = {"pdf": save_report_pdf, "docx": save_report_docx, "txt": save_report_txt}[ext]
                exporter(path, self.latest_report)
                QMessageBox.information(self, "Report exported", f"Saved the current processing report.\n{path}")
        except Exception as error:
            QMessageBox.critical(self, "Download failed", f"Could not complete this export.\n\n{error}")

    def apply_theme(self):

        theme = self.active_theme()
        self.day_night_button.setText("☀ DAY" if self.is_night_mode else "☾ NIGHT")

        fonts = resolve_fonts(theme)

        app = QApplication.instance()

        app.setPalette(
            build_palette(theme)
        )

        app.setFont(
            make_font(
                fonts,
                theme["scale"],
                "body",
                13,
            )
        )

        self.setStyleSheet(
            build_stylesheet(
                theme,
                chevron_path(theme["ink"]),
            )
        )

        self.database_view.setStyleSheet(
            build_database_stylesheet(theme)
        )

        self.sqlplus_panel.apply_theme(
            theme
        )

        self.analysis_panel.apply_theme(
            theme
        )

        apply_typography(
            self,
            theme,
            fonts,
            self.database_view,
        )

        self.refresh_active_buttons()

        self.status_label.setText(
            self.status_label.text()
        )

        if self.current_profile:

            self.set_account_status(
                f"● {self.current_profile.database_type.upper()} • "
                f"{self.current_profile.username}@"
                f"{self.current_profile.host}",
                "ok",
            )

        else:

            self.set_account_status(
                "● NOT CONNECTED",
                "wait",
            )


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(sys.argv)

    # Hide the tiny inherited icon at the left of each title bar while keeping
    # standard Windows title bars, close buttons, and window controls intact.
    blank_icon_pixmap = QPixmap(32, 32)
    blank_icon_pixmap.fill(Qt.GlobalColor.transparent)
    app.setWindowIcon(QIcon(blank_icon_pixmap))

    # Fusion renders consistently on every OS and honours our palette.
    app.setStyle("Fusion")

    app.setApplicationName("QRYVANTA")

    app.setOrganizationName("QRYVANTA")

    load_bundled_fonts()

    window = QRYVANTAWindow()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

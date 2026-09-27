"""Shared Qt dialog primitives used by the application and utilities."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox


def _application() -> QApplication:
    application = QApplication.instance()
    return application or QApplication([])


def ask_integer(message: str, title: str, default: int = 0, lowerbound: int = -2147483648, upperbound: int = 2147483647) -> int | None:
    _application()
    value, accepted = QInputDialog.getInt(None, title, message, default, lowerbound, upperbound)
    return value if accepted else None


def ask_float(message: str, title: str, default: float = 0.0, lowerbound: float = -1e12, upperbound: float = 1e12) -> float | None:
    _application()
    value, accepted = QInputDialog.getDouble(None, title, message, default, lowerbound, upperbound)
    return value if accepted else None


def ask_text(message: str, title: str, default: str = "") -> str | None:
    _application()
    value, accepted = QInputDialog.getText(None, title, message, text=default)
    return value if accepted else None


def ask_choice(message: str, title: str, choices: list[Any] | tuple[Any, ...]) -> Any:
    _application()
    values = [str(choice) for choice in choices]
    value, accepted = QInputDialog.getItem(None, title, message, values, 0, False)
    return value if accepted else None


def ask_yes_no(message: str, title: str) -> bool:
    _application()
    return QMessageBox.question(None, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


def ask_buttons(message: str, title: str, choices: list[str] | tuple[str, ...]) -> str | None:
    _application()
    box = QMessageBox(QMessageBox.Icon.Question, title, message)
    buttons = {box.addButton(choice, QMessageBox.ButtonRole.AcceptRole): choice for choice in choices}
    box.exec()
    clicked = box.clickedButton()
    return buttons.get(clicked)


def ask_multiple(message: str, title: str, fields: list[str], defaults: list[str] | None = None) -> list[str] | None:
    values: list[str] = []
    defaults = defaults or [""] * len(fields)
    for field, default in zip(fields, defaults):
        value = ask_text(f"{message}\n{field}", title, default)
        if value is None:
            return None
        values.append(value)
    return values


def choose_directory(title: str = "Choose a directory") -> str | None:
    _application()
    value = QFileDialog.getExistingDirectory(None, title)
    return value or None


def choose_file(title: str = "Choose a file", file_filter: str = "All files (*)", multiple: bool = False) -> str | list[str] | None:
    _application()
    if multiple:
        values, _ = QFileDialog.getOpenFileNames(None, title, "", file_filter)
        return values or None
    value, _ = QFileDialog.getOpenFileName(None, title, "", file_filter)
    return value or None


def save_file(title: str = "Save file", file_filter: str = "All files (*)") -> str | None:
    _application()
    value, _ = QFileDialog.getSaveFileName(None, title, "", file_filter)
    return value or None


def show_message(message: str, title: str = "Information") -> None:
    _application()
    QMessageBox.information(None, title, message)

"""Konstanta lembar gaya QSS gelap bersama untuk dialog modul Tambah Stok."""

from __future__ import annotations

DIALOG_STYLESHEET: str = """
QDialog {
    background-color: #161622;
    color: #CDD6F4;
    font-family: "Segoe UI", "Inter", sans-serif;
}
QFrame#dialogCard {
    background-color: #1E1E2E;
    border: 1px solid #313244;
    border-radius: 10px;
}
QLabel#dialogTitle {
    color: #CDD6F4;
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}
QLabel#dialogSubtitle {
    color: #A6ADC8;
    font-size: 12px;
    background: transparent;
}
QLabel#fieldLabel {
    color: #A6ADC8;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLabel#errorLabel {
    color: #F38BA8;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}
QLineEdit, QComboBox, QDateTimeEdit, QSpinBox {
    background-color: #11111B;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus, QSpinBox:focus {
    border: 1px solid #89B4FA;
}
QComboBox QAbstractItemView {
    background-color: #1E1E2E;
    color: #CDD6F4;
    border: 1px solid #45475A;
    selection-background-color: #313244;
    selection-color: #89B4FA;
}
QCheckBox {
    color: #CDD6F4;
    font-size: 12px;
    spacing: 6px;
}
QTableWidget {
    background-color: #11111B;
    alternate-background-color: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 8px;
    outline: none;
    selection-background-color: #25283D;
    selection-color: #CDD6F4;
}
QTableWidget::item {
    border-bottom: 1px solid #242538;
    padding: 4px 6px;
}
QTableWidget QHeaderView::section {
    background-color: #1E1E2E;
    color: #A6ADC8;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 7px 8px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#primaryBtn {
    background-color: #A6E3A1;
    color: #11111B;
    border: none;
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#primaryBtn:hover {
    background-color: #B8EBB3;
}
QPushButton#accentBtn {
    background-color: #89B4FA;
    color: #11111B;
    border: none;
    border-radius: 7px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#accentBtn:hover {
    background-color: #A0C4FF;
}
QPushButton#secondaryBtn {
    background-color: #2A2A40;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 7px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#secondaryBtn:hover {
    background-color: #34344E;
}
"""

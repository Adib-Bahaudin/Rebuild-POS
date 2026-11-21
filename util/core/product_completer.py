from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QStringListModel, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QCompleter, QLineEdit

if TYPE_CHECKING:
    from core.transaksi_backend import CatalogProduct, TransactionRepository

logger = logging.getLogger(__name__)


class ProductSearchCompleter(QObject):
    """Mengelola dropdown autocomplete pencarian produk berbasis database."""

    product_selected = Signal(object)

    def __init__(
        self,
        search_input: QLineEdit,
        category_combo: QComboBox,
        repository: TransactionRepository,
        max_items: int = 10,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent or search_input)
        self._search_input = search_input
        self._category_combo = category_combo
        self._repository = repository
        self._max_items = max_items
        self._label_to_product: dict[str, CatalogProduct] = {}

        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self._search_input)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self._completer.setMaxVisibleItems(self._max_items)

        popup = self._completer.popup()
        if popup is not None:
            popup.setStyleSheet(
                """
                QListView {
                    background-color: #11111B;
                    color: #CDD6F4;
                    border: 1px solid #313244;
                    selection-background-color: #0078D7;
                    padding: 4px;
                }
                """
            )
        self._search_input.setCompleter(self._completer)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._fetch_suggestions)

        self._search_input.textEdited.connect(self._on_text_edited)
        self._category_combo.currentTextChanged.connect(self._on_category_changed)
        self._completer.activated.connect(self._on_item_activated)

    def _hide_popup(self) -> None:
        popup = self._completer.popup()
        if popup is not None:
            popup.hide()

    def _on_text_edited(self, text: str) -> None:
        if not text.strip():
            self._label_to_product.clear()
            self._model.setStringList([])
            self._hide_popup()
            return
        self._timer.start()

    def _on_category_changed(self, _category: str) -> None:
        if self._search_input.text().strip():
            self._timer.start()

    def _fetch_suggestions(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            return

        category = self._category_combo.currentText()
        try:
            matches = self._repository.search_catalog(query, category)
        except Exception as exc:
            logger.warning("Gagal memuat saran autocomplete: %s", exc)
            return

        self._label_to_product.clear()
        labels: list[str] = []
        for product in matches[: self._max_items]:
            label = (
                f"[{product.sku}] {product.display_name} - "
                f"Rp {product.selling_price:,}".replace(",", ".")
            )
            self._label_to_product[label] = product
            labels.append(label)

        self._model.setStringList(labels)

        if labels:
            self._completer.complete()
        else:
            self._hide_popup()

    def _on_item_activated(self, text: str) -> None:
        selected = self._label_to_product.get(text)
        if selected is not None:
            self.product_selected.emit(selected)
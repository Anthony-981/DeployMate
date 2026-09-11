import re

from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from PySide6.QtCore import QDate, QEvent, QPoint, QPointF, QTimer, Qt, QObject
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPalette, QKeySequence
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QCompleter


class PasswordLineEdit(QLineEdit):
    """Password field with an explicit show/hide control."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setEchoMode(QLineEdit.Normal)
        self.toggle_button = QToolButton(self)
        self.toggle_button.setText("隐藏")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setFocusPolicy(Qt.NoFocus)
        self.toggle_button.setStyleSheet(
            "QToolButton { color: #315dd3; border: none; padding: 0 6px; font-weight: 700; }"
            "QToolButton:hover { color: #2148ac; background: #edf4ff; border-radius: 5px; }"
        )
        self.toggle_button.clicked.connect(self.toggle_password)
        self._update_button_geometry()

    def toggle_password(self):
        visible = self.echoMode() == QLineEdit.Normal
        self.setEchoMode(QLineEdit.Password if visible else QLineEdit.Normal)
        self.toggle_button.setText("显示" if visible else "隐藏")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_button_geometry()

    def _update_button_geometry(self):
        if hasattr(self, "toggle_button"):
            width = 46
            self.toggle_button.setGeometry(self.width() - width - 2, 2, width, max(20, self.height() - 4))
            self.setTextMargins(0, 0, width + 2, 0)


class PaginationBar(QWidget):
    page_changed = Signal(int)

    def __init__(self, page_size=20, parent=None):
        super().__init__(parent)
        self.page_size = page_size
        self.page = 1
        self.total = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self.summary = QLabel()
        self.previous = make_button("上一页")
        self.next = make_button("下一页")
        self.previous.clicked.connect(lambda: self._change(-1))
        self.next.clicked.connect(lambda: self._change(1))
        self.pages_layout = QHBoxLayout()
        self.pages_layout.setSpacing(4)
        layout.addWidget(self.summary)
        layout.addStretch()
        layout.addLayout(self.pages_layout)
        layout.addWidget(self.previous)
        layout.addWidget(self.next)
        self._update()

    @property
    def page_count(self):
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    def set_total(self, total):
        self.total = max(0, int(total))
        adjusted = self.page > self.page_count
        self.page = min(self.page, self.page_count)
        self._update()
        return adjusted

    def reset(self):
        """Return to the first page when the current data scope changes."""
        if self.page != 1:
            self.page = 1
        self._update()

    def set_page(self, page):
        page = max(1, min(int(page), self.page_count))
        if page != self.page:
            self.page = page
            self._update()
            self.page_changed.emit(page)

    def _change(self, offset):
        self.set_page(self.page + offset)

    def _update(self):
        self.summary.setText(f"共 {self.total} 条 | 第 {self.page} / {self.page_count} 页 | 每页 {self.page_size} 条")
        self.previous.setEnabled(self.page > 1)
        self.next.setEnabled(self.page < self.page_count)
        while self.pages_layout.count():
            item = self.pages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if self.page_count <= 7:
            numbers = list(range(1, self.page_count + 1))
        else:
            numbers = [1, 2, self.page_count - 1, self.page_count]
            numbers.extend([self.page - 1, self.page, self.page + 1])
            numbers = sorted({number for number in numbers if 1 <= number <= self.page_count})
        previous_number = None
        for number in numbers:
            if previous_number is not None and number - previous_number > 1:
                ellipsis = QLabel("更多")
                ellipsis.setAlignment(Qt.AlignCenter)
                ellipsis.setFixedWidth(38)
                ellipsis.setStyleSheet("color: #7b8ba4; font-weight: 800;")
                self.pages_layout.addWidget(ellipsis)
            button = make_button(str(number))
            button.setFixedWidth(40)
            button.setEnabled(number != self.page)
            if number == self.page:
                button.setStyleSheet("QPushButton { background: #3f7dff; color: white; border-radius: 7px; font-weight: 800; }")
            button.clicked.connect(lambda _checked=False, value=number: self.set_page(value))
            self.pages_layout.addWidget(button)
            previous_number = number


class _ComboClickFilter(QObject):
    """Open a searchable combo when the user clicks its text area or arrow."""

    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if watched is self.combo.lineEdit() or watched is self.combo:
                self.combo.lineEdit().selectAll()
                QTimer.singleShot(0, self.combo.showPopup)
                return True
        return False


def build_chinese_context_menu(widget):
    """Build a Chinese context menu for an editor or table."""
    menu = QMenu(widget)
    if isinstance(widget, QTableWidget):
        copy_action = menu.addAction("复制选中内容")
        copy_action.setEnabled(bool(widget.selectedRanges()) or bool(widget.currentItem()))
        def copy_table_selection():
            if hasattr(widget, "copy_selection_to_clipboard"):
                widget.copy_selection_to_clipboard()
                return
            ranges = widget.selectedRanges()
            if not ranges and widget.currentItem():
                QGuiApplication.clipboard().setText(widget.currentItem().text())
                return
            if not ranges:
                return
            selected = ranges[0]
            lines = []
            for row in range(selected.topRow(), selected.bottomRow() + 1):
                lines.append("\t".join(
                    widget.item(row, column).text() if widget.item(row, column) else ""
                    for column in range(selected.leftColumn(), selected.rightColumn() + 1)
                ))
            QGuiApplication.clipboard().setText("\n".join(lines))

        copy_action.triggered.connect(copy_table_selection)
        select_action = menu.addAction("全选")
        select_action.triggered.connect(widget.selectAll)
        clear_action = menu.addAction("取消选择")
        clear_action.triggered.connect(widget.clearSelection)
        return menu

    has_selection = bool(widget.selectedText()) if isinstance(widget, QLineEdit) else bool(widget.textCursor().hasSelection())
    read_only = widget.isReadOnly()
    undo_action = menu.addAction("撤销")
    undo_action.setEnabled(widget.isUndoAvailable())
    undo_action.triggered.connect(widget.undo)
    redo_action = menu.addAction("重做")
    redo_action.setEnabled(widget.isRedoAvailable())
    redo_action.triggered.connect(widget.redo)
    menu.addSeparator()
    cut_action = menu.addAction("剪切")
    cut_action.setEnabled(has_selection and not read_only)
    cut_action.triggered.connect(widget.cut)
    copy_action = menu.addAction("复制")
    copy_action.setEnabled(has_selection)
    copy_action.triggered.connect(widget.copy)
    paste_action = menu.addAction("粘贴")
    paste_action.setEnabled(not read_only)
    paste_action.triggered.connect(widget.paste)
    delete_action = menu.addAction("删除")
    delete_action.setEnabled(has_selection and not read_only)

    def delete_selection():
        if isinstance(widget, QLineEdit):
            start = widget.selectionStart()
            end = start + len(widget.selectedText())
            widget.setText(widget.text()[:start] + widget.text()[end:])
            widget.setCursorPosition(start)
        else:
            cursor = widget.textCursor()
            cursor.removeSelectedText()
            widget.setTextCursor(cursor)

    delete_action.triggered.connect(delete_selection)
    select_action = menu.addAction("全选")
    select_action.triggered.connect(widget.selectAll)
    return menu


class ChineseContextMenuFilter(QObject):
    """Replace native edit menus so right-click actions stay in Chinese."""

    def eventFilter(self, watched, event):
        if event.type() != QEvent.ContextMenu:
            return False
        target = watched
        if isinstance(watched, QWidget) and isinstance(watched.parentWidget(), QTableWidget):
            target = watched.parentWidget()
        if not isinstance(target, (QLineEdit, QTextEdit, QTableWidget)):
            return False
        if isinstance(target, QTableWidget):
            local_pos = watched.mapTo(target.viewport(), event.pos()) if isinstance(watched, QWidget) else event.pos()
            item = target.itemAt(local_pos)
            if item and not item.isSelected():
                target.clearSelection()
                target.setCurrentItem(item)
                item.setSelected(True)
        menu = build_chinese_context_menu(target)
        menu.exec(event.globalPos())
        return True


class PasswordCellWidget(QWidget):
    """Masked password display for a table cell with a per-row toggle."""

    def __init__(self, password="", parent=None):
        super().__init__(parent)
        self._password = str(password or "")
        self._visible = True
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignCenter)
        self.toggle_button = QToolButton()
        self.toggle_button.setText("隐藏")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setFocusPolicy(Qt.NoFocus)
        self.toggle_button.setFixedWidth(42)
        self.toggle_button.setStyleSheet(
            "QToolButton { color: #315dd3; border: 1px solid #d4e3fb; border-radius: 5px; "
            "background: #f4f8ff; padding: 2px 4px; font-weight: 700; }"
            "QToolButton:hover { background: #e6efff; }"
        )
        self.toggle_button.clicked.connect(self.toggle_password)
        layout.addWidget(self.value_label, 1)
        layout.addWidget(self.toggle_button)
        self._refresh()

    def toggle_password(self):
        self._visible = not self._visible
        self._refresh()

    def _refresh(self):
        self.value_label.setText(self._password if self._visible else ("******" if self._password else ""))
        self.toggle_button.setText("隐藏" if self._visible else "显示")

APP_STYLESHEET = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    color: #0f1f3a;
}
QMainWindow {
    background: #edf3fb;
}
QDialog, QMessageBox {
    background: #f8fbff;
}
QToolTip {
    background: #ffffff;
    color: #24344f;
    border: 1px solid #cbd9eb;
    padding: 6px 9px;
    border-radius: 6px;
}
QDialog#formDialog {
    background: #f5f8fc;
}
QDialog#formDialog QFrame#dialogBody {
    background: #ffffff;
    border: 1px solid #dfe8f5;
    border-radius: 12px;
}
QMessageBox QLabel {
    color: #0f1f3a;
    min-width: 260px;
    font-size: 14px;
}
QMessageBox QPushButton {
    background: #3f7dff;
    color: white;
    border: 1px solid #356fe3;
    min-width: 76px;
}
QMessageBox QPushButton:hover {
    background: #356fe3;
}
QFrame#contentShell {
    background: #f8fbff;
    border: 1px solid #dbe5f2;
    border-radius: 24px;
}
QFrame#cardFrame, QFrame#panelFrame {
    background: white;
    border: 1px solid #dfe8f5;
    border-radius: 16px;
}
QLabel {
    background: transparent;
}
QLineEdit, QComboBox, QDateEdit, QTextEdit {
    background: #fbfdff;
    border: 1px solid #d8e2ef;
    border-radius: 10px;
    padding: 8px 10px;
    min-height: 18px;
    selection-background-color: #3f7dff;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {
    border: 1px solid #3f7dff;
    background: white;
}
QDateEdit {
    min-height: 20px;
    padding-right: 38px;
    font-weight: 600;
}
QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 34px;
    border: none;
    border-left: 1px solid #d8e2ef;
    border-top-right-radius: 9px;
    border-bottom-right-radius: 9px;
    background: #edf4ff;
}
QDateEdit::drop-down:hover {
    background: #dfeaff;
}
QCalendarWidget {
    background: white;
    border: 1px solid #d8e2ef;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: #f1f6ff;
    border-bottom: 1px solid #dfe8f5;
    padding: 6px;
}
QCalendarWidget QToolButton {
    color: #244783;
    background: transparent;
    border: none;
    border-radius: 6px;
    min-height: 30px;
    padding: 0 8px;
}
QCalendarWidget QToolButton:hover {
    background: #dfeaff;
}
QCalendarWidget QSpinBox {
    background: white;
    border: 1px solid #d8e2ef;
    border-radius: 6px;
    padding: 4px 8px;
}
QCalendarWidget QAbstractItemView {
    background: white;
    color: #24344f;
    selection-background-color: #3f7dff;
    selection-color: white;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: white;
    border: 1px solid #dfe8f5;
    selection-background-color: #eaf2ff;
}
QPushButton {
    border: none;
    border-radius: 10px;
    padding: 0 14px;
    min-height: 38px;
    font-weight: 700;
}
QPushButton:hover {
    opacity: 0.96;
}
QPushButton:pressed {
    padding-top: 1px;
}
QTableWidget {
    background: white;
    border: 1px solid #e4ebf4;
    border-radius: 12px;
    gridline-color: #edf1f7;
    alternate-background-color: #f9fbfe;
    color: #0f1f3a;
    selection-background-color: #eaf2ff;
    selection-color: #0f1f3a;
}
QTableWidget::item {
    padding: 6px 8px;
    background: transparent;
    color: #0f1f3a;
}
QTableWidget::item:hover {
    background: #f2f7ff;
    color: #0f1f3a;
}
QTableWidget::item:selected {
    background: #dce9ff;
    color: #0f1f3a;
}
QTableWidget:focus {
    outline: none;
    border: 1px solid #9dbcf0;
}
QAbstractItemView {
    background: #ffffff;
    color: #0f1f3a;
    selection-background-color: #dce9ff;
    selection-color: #0f1f3a;
}
QAbstractItemView::item:hover {
    background: #f2f7ff;
    color: #0f1f3a;
}
QAbstractItemView::item:selected {
    background: #dce9ff;
    color: #0f1f3a;
}
QMenu {
    background: #ffffff;
    color: #0f1f3a;
    border: 1px solid #dfe8f5;
}
QMenu::item {
    background: transparent;
    color: #0f1f3a;
    padding: 7px 28px 7px 16px;
}
QMenu::item:selected {
    background: #eaf2ff;
    color: #0f1f3a;
}
QComboBox QAbstractItemView::item {
    min-height: 30px;
}
QHeaderView::section {
    background: #f7faff;
    color: #425069;
    border: none;
    border-bottom: 1px solid #e4ebf4;
    padding: 10px 8px;
    font-weight: 700;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 8px 2px 8px 2px;
}
QScrollBar::handle:vertical {
    background: #c9d8ec;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #b2c7e2;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px 8px 2px 8px;
}
QScrollBar::handle:horizontal {
    background: #c9d8ec;
    border-radius: 5px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: #b2c7e2;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""

CALENDAR_STYLESHEET = """
QCalendarWidget {
    background-color: #ffffff;
    color: #24344f;
    border: 1px solid #cbd9eb;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #f1f6ff;
    border-bottom: 1px solid #dfe8f5;
    padding: 6px;
}
QCalendarWidget QToolButton {
    color: #244783;
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-height: 30px;
    padding: 0 8px;
}
QCalendarWidget QToolButton:hover {
    background-color: #dfeaff;
}
QCalendarWidget QMenu {
    color: #24344f;
    background-color: #ffffff;
    border: 1px solid #d8e2ef;
}
QCalendarWidget QSpinBox {
    color: #24344f;
    background-color: #ffffff;
    border: 1px solid #d8e2ef;
    border-radius: 6px;
    padding: 4px 8px;
}
QCalendarWidget QAbstractItemView:enabled {
    color: #24344f;
    background-color: #ffffff;
    alternate-background-color: #ffffff;
    selection-background-color: #3f7dff;
    selection-color: #ffffff;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #a4afc0;
    background-color: #ffffff;
}
"""


class LimitedTextEdit(QTextEdit):
    def __init__(self, max_chars: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_chars = max_chars
        self._guard = False
        self.textChanged.connect(self._enforce_limit)

    def _enforce_limit(self):
        if self._guard:
            return
        text = self.toPlainText()
        if len(text) <= self.max_chars:
            return
        self._guard = True
        self.setPlainText(text[: self.max_chars])
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self._guard = False


class ClickableDateEdit(QDateEdit):
    """Open the native calendar when the user clicks anywhere in the date field."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().x() < self.width() - 34:
            local_pos = QPointF(self.width() - 12, self.height() / 2)
            global_pos = QPointF(self.mapToGlobal(local_pos.toPoint()))
            press = QMouseEvent(
                QEvent.MouseButtonPress,
                local_pos,
                global_pos,
                Qt.LeftButton,
                Qt.LeftButton,
                event.modifiers(),
            )
            QDateEdit.mousePressEvent(self, press)
            return
        super().mousePressEvent(event)


class FormDialog(QDialog):
    def __init__(self, title: str, subtitle: str, fields, columns: int = 2,
                 field_width: int = 320, width: int = 820, height: int = 520, parent=None):
        super().__init__(parent)
        self.setObjectName("formDialog")
        self.setStyleSheet(APP_STYLESHEET)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(width, height)
        self.setMinimumSize(min(width, 680), min(height, 420))

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 22px; font-weight: 800; color: #0f1f3a;")
        root.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setStyleSheet("font-size: 13px; color: #627189;")
            root.addWidget(subtitle_label)

        body = QFrame()
        body.setObjectName("dialogBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.addLayout(make_compact_form(fields, columns=columns, field_width=field_width))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = make_button("取消")
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.save_button = make_button("保存", True)
        actions.addWidget(self.save_button)
        self.actions_layout = actions
        root.addLayout(actions)


def confirm_action(parent, title: str, message: str) -> bool:
    dialog = QDialog(parent)
    dialog.setObjectName("formDialog")
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setStyleSheet(APP_STYLESHEET)
    dialog.setFixedWidth(460)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(16)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #0f1f3a;")
    layout.addWidget(title_label)
    message_label = QLabel(message)
    message_label.setWordWrap(True)
    message_label.setStyleSheet("font-size: 14px; color: #52627a; line-height: 1.5;")
    layout.addWidget(message_label)
    actions = QHBoxLayout()
    actions.addStretch()
    cancel_button = make_button("取消")
    cancel_button.clicked.connect(dialog.reject)
    actions.addWidget(cancel_button)
    confirm_button = make_button("确认删除", True)
    confirm_button.setStyleSheet("""
        QPushButton { background: #d94848; color: white; border-radius: 10px; padding: 0 16px; }
        QPushButton:hover { background: #c83c3c; }
    """)
    confirm_button.clicked.connect(dialog.accept)
    actions.addWidget(confirm_button)
    layout.addLayout(actions)
    return dialog.exec() == QDialog.Accepted


def make_management_toolbar(add_text: str = "添加"):
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    search_edit = QLineEdit()
    search_edit.setPlaceholderText("搜索列表...")
    search_edit.setClearButtonEnabled(True)
    search_edit.setMaximumWidth(320)
    layout.addWidget(search_edit)
    layout.addStretch()
    refresh_button = make_button("刷新")
    edit_button = make_button("编辑")
    delete_button = make_button("批量删除")
    delete_button.setToolTip("删除当前表格中选中的一条或多条记录")
    add_button = make_button(add_text, True)
    for button in (refresh_button, edit_button, delete_button, add_button):
        layout.addWidget(button)
    return layout, search_edit, refresh_button, edit_button, delete_button, add_button


def make_searchable_combo(combo: QComboBox) -> QComboBox:
    """Enable contains-matching completion without allowing arbitrary values."""
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.setMaxVisibleItems(12)
    combo.view().setMinimumWidth(360)
    combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    combo.view().setStyleSheet("QAbstractItemView { background: #ffffff; color: #24344f; selection-background-color: #e7f0ff; selection-color: #163b80; padding: 4px; }")
    combo.setCompleter(QCompleter(combo.model(), combo))
    completer = combo.completer()
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    # QComboBox keeps the previous item index while its editable text changes.
    # Clear that stale index during typing, then restore it when a completion is chosen.
    def clear_stale_index(text):
        if combo.currentIndex() >= 0 and combo.itemText(combo.currentIndex()) != text:
            combo.setCurrentIndex(-1)

    def activate_completion(text):
        index = combo.findText(text, Qt.MatchFixedString)
        if index >= 0:
            combo.setCurrentIndex(index)

    combo.lineEdit().textEdited.connect(clear_stale_index)
    completer.activated[str].connect(activate_completion)
    combo.lineEdit().returnPressed.connect(
        lambda: activate_completion(combo.currentText())
    )
    click_filter = _ComboClickFilter(combo)
    combo.installEventFilter(click_filter)
    combo.lineEdit().installEventFilter(click_filter)
    combo.setProperty("comboClickFilter", click_filter)
    combo.setMaxVisibleItems(12)
    combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    combo.view().setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    combo.view().setStyleSheet("""
        QListView { background: #ffffff; color: #24344f; border: 1px solid #cbd9eb; padding: 4px; }
        QListView::item { min-height: 32px; padding: 6px 10px; }
        QListView::item:hover { background: #edf4ff; color: #2148ac; }
        QListView::item:selected { background: #3f7dff; color: #ffffff; }
        QScrollBar:vertical { width: 10px; background: #f4f7fb; margin: 2px; }
        QScrollBar::handle:vertical { background: #b9cbe7; border-radius: 5px; min-height: 28px; }
        QScrollBar::handle:vertical:hover { background: #8eadd9; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    """)
    return combo


def display_project_name(name: str) -> str:
    """Hide generated IMPORT suffixes from project labels shown to users."""
    value = str(name or "-")
    # Imported projects may have been created by older versions with different
    # separators. Keep the user-facing project name and hide the generated code.
    cleaned = re.split(r"\s*/?\s*IMPORT\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip() or value


def selected_record_ids(table: QTableWidget) -> list[int]:
    rows = sorted({index.row() for index in table.selectionModel().selectedRows()})
    if not rows:
        rows = sorted({index.row() for index in table.selectionModel().selectedIndexes()})
    if not rows and table.currentRow() >= 0:
        rows = [table.currentRow()]
    result = []
    for row in rows:
        item = table.item(row, 0)
        if item and item.text().strip().isdigit():
            result.append(int(item.text()))
    return result


def filter_table(table: QTableWidget, search_text: str):
    keyword = (search_text or "").strip().lower()
    for row in range(table.rowCount()):
        values = []
        for column in range(table.columnCount()):
            if table.isColumnHidden(column):
                continue
            item = table.item(row, column)
            if item:
                values.append(item.text())
            widget = table.cellWidget(row, column)
            if widget:
                values.extend(child.text() for child in widget.findChildren(QLabel) if child.text())
                values.extend(child.text() for child in widget.findChildren(QLineEdit) if child.text())
        matched = not keyword or any(keyword in value.lower() for value in values)
        table.setRowHidden(row, not matched)


def add_table_actions(table: QTableWidget, record_ids, on_edit, on_delete, column: int = 1):
    if isinstance(table, ManagedTableWidget):
        table.set_pinned_actions(record_ids, on_edit, on_delete, column)
        return
    for row, record_id in enumerate(record_ids):
        table.setCellWidget(row, column, _make_action_cell(record_id, on_edit, on_delete))
    table.setColumnWidth(column, 126)


def _make_action_cell(record_id, on_edit, on_delete):
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    actions = QHBoxLayout(container)
    actions.setContentsMargins(0, 0, 0, 0)
    actions.setSpacing(6)
    actions.setAlignment(Qt.AlignCenter)
    edit_button = QPushButton("编辑")
    edit_button.setFixedSize(50, 30)
    edit_button.setCursor(Qt.PointingHandCursor)
    edit_button.setFocusPolicy(Qt.NoFocus)
    edit_button.setStyleSheet("""
        QPushButton {
            background: #edf4ff;
            color: #315dd3;
            border: 1px solid #cbdcf9;
            border-radius: 7px;
            padding: 0px;
            min-width: 48px;
            max-width: 48px;
            min-height: 28px;
            max-height: 28px;
            font-weight: 700;
        }
        QPushButton:hover { background: #dce8ff; border-color: #9dbbf2; }
        QPushButton:pressed { background: #cfdeff; }
    """)
    delete_button = QPushButton("删除")
    delete_button.setFixedSize(50, 30)
    delete_button.setCursor(Qt.PointingHandCursor)
    delete_button.setFocusPolicy(Qt.NoFocus)
    delete_button.setStyleSheet("""
        QPushButton {
            background: #fff3f3;
            color: #c33d3d;
            border: 1px solid #f0cccc;
            border-radius: 7px;
            padding: 0px;
            min-width: 48px;
            max-width: 48px;
            min-height: 28px;
            max-height: 28px;
            font-weight: 700;
        }
        QPushButton:hover { background: #ffe3e3; border-color: #e9aaaa; }
        QPushButton:pressed { background: #ffd6d6; }
    """)
    edit_button.clicked.connect(lambda _checked=False, item_id=record_id: on_edit(item_id))
    delete_button.clicked.connect(lambda _checked=False, item_id=record_id: on_delete(item_id))
    actions.addWidget(edit_button)
    actions.addWidget(delete_button)
    return container


class ManagedTableWidget(QTableWidget):
    PINNED_WIDTH = 124

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pinned_actions = None
        self._action_source_column = None
        self._action_id_column = 0
        self._on_edit = None
        self._on_delete = None
        self._record_id_lookup = {}
        self._sort_sync_connected = False
        self.action_header_label = None
        self._light_tooltip = None

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy) or (event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier):
            self.copy_selection_to_clipboard()
            return
        super().keyPressEvent(event)

    def copy_selection_to_clipboard(self):
        ranges = self.selectedRanges()
        if not ranges and self.currentItem():
            QGuiApplication.clipboard().setText(self.currentItem().text())
            return
        if not ranges:
            return
        selected = ranges[0]
        lines = []
        for row in range(selected.topRow(), selected.bottomRow() + 1):
            lines.append("\t".join(
                self.item(row, column).text() if self.item(row, column) else ""
                for column in range(selected.leftColumn(), selected.rightColumn() + 1)
            ))
        QGuiApplication.clipboard().setText("\n".join(lines))

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item and not item.isSelected():
            self.clearSelection()
            self.setCurrentItem(item)
            item.setSelected(True)
        menu = build_chinese_context_menu(self)
        menu.exec(event.globalPos())

    def set_pinned_actions(self, record_ids, on_edit, on_delete, source_column: int):
        self._action_source_column = source_column
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._record_id_lookup = {str(record_id): record_id for record_id in record_ids}
        self.setColumnHidden(source_column, True)
        if self.pinned_actions is None:
            pinned = QTableWidget(self)
            pinned.setObjectName("pinnedActions")
            pinned.setColumnCount(1)
            pinned.verticalHeader().setVisible(False)
            pinned.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
            pinned.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
            pinned.setColumnWidth(0, self.PINNED_WIDTH - 2)
            pinned.setFixedWidth(self.PINNED_WIDTH)
            pinned.setFocusPolicy(Qt.NoFocus)
            pinned.setSelectionMode(QAbstractItemView.NoSelection)
            pinned.setEditTriggers(QAbstractItemView.NoEditTriggers)
            pinned.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            pinned.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            pinned.setShowGrid(False)
            pinned.setAlternatingRowColors(True)
            pinned.setStyleSheet("""
                QTableWidget#pinnedActions {
                    background: white;
                    border: none;
                    border-left: 1px solid #d5e0ee;
                    alternate-background-color: #f9fbfe;
                }
                QTableWidget#pinnedActions::item {
                    border-bottom: 1px solid #edf1f7;
                }
                QTableWidget#pinnedActions QHeaderView::section {
                    background: #eef4fc;
                    color: #344660;
                    border: none;
                    border-left: 1px solid #d5e0ee;
                    border-bottom: 1px solid #dfe7f2;
                    padding: 10px 8px;
                    font-weight: 800;
                }
            """)
            self.pinned_actions = pinned
            self.action_header_label = QLabel("操作", pinned)
            self.action_header_label.setObjectName("pinnedActionHeader")
            self.action_header_label.setAlignment(Qt.AlignCenter)
            self.action_header_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.action_header_label.setStyleSheet("""
                QLabel#pinnedActionHeader {
                    background: #eef4fc;
                    color: #344660;
                    border: none;
                    border-left: 1px solid #d5e0ee;
                    border-bottom: 1px solid #dfe7f2;
                    font-weight: 800;
                }
            """)
            self.verticalScrollBar().valueChanged.connect(pinned.verticalScrollBar().setValue)
            pinned.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)

        self._populate_pinned_actions(record_ids)
        self.setViewportMargins(0, 0, self.PINNED_WIDTH, 0)
        if not self._sort_sync_connected:
            self.horizontalHeader().sortIndicatorChanged.connect(self._schedule_action_sync)
            self._sort_sync_connected = True
        self.pinned_actions.show()
        self.pinned_actions.raise_()
        self._sync_pinned_geometry()
        QTimer.singleShot(0, self._sync_pinned_geometry)

    def _populate_pinned_actions(self, record_ids):
        pinned = self.pinned_actions
        pinned.clearContents()
        pinned.setRowCount(len(record_ids))
        header_item = QTableWidgetItem("操作")
        header_item.setTextAlignment(Qt.AlignCenter)
        pinned.setHorizontalHeaderItem(0, header_item)
        header_height = self.horizontalHeader().height()
        pinned.horizontalHeader().setFixedHeight(header_height)
        self.action_header_label.setGeometry(0, 0, self.PINNED_WIDTH, header_height)
        self.action_header_label.show()
        self.action_header_label.raise_()
        for row, record_id in enumerate(record_ids):
            pinned.setRowHeight(row, self.rowHeight(row))
            pinned.setCellWidget(row, 0, _make_action_cell(record_id, self._on_edit, self._on_delete))
            pinned.setRowHidden(row, self.isRowHidden(row))

    def _schedule_action_sync(self, *_args):
        QTimer.singleShot(0, self._sync_actions_to_visible_rows)

    def _sync_actions_to_visible_rows(self):
        if not self.pinned_actions:
            return
        record_ids = []
        for row in range(self.rowCount()):
            item = self.item(row, self._action_id_column)
            text_id = item.text() if item else ""
            record_ids.append(self._record_id_lookup.get(text_id, text_id))
        self._populate_pinned_actions(record_ids)

    def sortItems(self, column: int, order=Qt.AscendingOrder):
        super().sortItems(column, order)
        if self.pinned_actions:
            self._sync_actions_to_visible_rows()

    def setRowHidden(self, row: int, hide: bool):
        super().setRowHidden(row, hide)
        if self.pinned_actions and row < self.pinned_actions.rowCount():
            self.pinned_actions.setRowHidden(row, hide)

    def _position_pinned_actions(self):
        if not self.pinned_actions:
            return
        frame = self.frameWidth()
        scroll_height = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        x = self.width() - self.PINNED_WIDTH - frame
        self.pinned_actions.setGeometry(
            x,
            frame,
            self.PINNED_WIDTH,
            self.height() - (2 * frame) - scroll_height,
        )
        self.pinned_actions.raise_()
        if self.action_header_label:
            self.action_header_label.setGeometry(
                0, 0, self.PINNED_WIDTH, self.pinned_actions.horizontalHeader().height()
            )
            self.action_header_label.raise_()

    def _sync_pinned_geometry(self):
        if not self.pinned_actions:
            return
        header_height = self.horizontalHeader().height()
        self.pinned_actions.horizontalHeader().setFixedHeight(header_height)
        for row in range(min(self.rowCount(), self.pinned_actions.rowCount())):
            self.pinned_actions.setRowHeight(row, self.rowHeight(row))
        self._position_pinned_actions()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_pinned_geometry()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_pinned_geometry()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if self.pinned_actions:
            self.pinned_actions.verticalScrollBar().setValue(self.verticalScrollBar().value())

    def _hide_light_tooltip(self):
        tooltip = self._light_tooltip
        self._light_tooltip = None
        if tooltip is not None:
            tooltip.hide()
            tooltip.deleteLater()

    def _hide_current_light_tooltip(self, tooltip):
        if self._light_tooltip is tooltip:
            self._hide_light_tooltip()

    def _show_light_tooltip(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            self._hide_light_tooltip()
            return True
        item = self.item(index.row(), index.column())
        text = item.text().strip() if item else ""
        if not text:
            self._hide_light_tooltip()
            return True

        self._hide_light_tooltip()
        tooltip = QLabel(text)
        tooltip.setObjectName("lightTableTooltip")
        tooltip.setWordWrap(True)
        tooltip.setMaximumWidth(440)
        tooltip.setAttribute(Qt.WA_ShowWithoutActivating)
        tooltip.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        tooltip.setStyleSheet("""
            QLabel#lightTableTooltip {
                background-color: #ffffff;
                color: #24344f;
                border: 1px solid #cbd9eb;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }
        """)
        tooltip.adjustSize()

        position = event.globalPos() + QPoint(14, 16)
        screen = QGuiApplication.screenAt(event.globalPos())
        if screen:
            area = screen.availableGeometry()
            position.setX(min(position.x(), area.right() - tooltip.width()))
            position.setY(min(position.y(), area.bottom() - tooltip.height()))
            position.setX(max(position.x(), area.left()))
            position.setY(max(position.y(), area.top()))
        tooltip.move(position)
        tooltip.show()
        tooltip.raise_()
        self._light_tooltip = tooltip
        QTimer.singleShot(3500, lambda: self._hide_current_light_tooltip(tooltip))
        return True

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            return self._show_light_tooltip(event)
        if event.type() in (QEvent.Leave, QEvent.MouseMove):
            self._hide_light_tooltip()
        return super().viewportEvent(event)


def show_toast(parent, message: str, success: bool = True, duration: int = 3200):
    host = parent.window() if parent else None
    if host is None:
        return
    toast = QFrame(host)
    toast.setObjectName("toastMessage")
    background = "#e9f8ef" if success else "#fff0f0"
    border = "#8bd3a8" if success else "#f0a0a0"
    color = "#17643a" if success else "#9f2929"
    toast.setStyleSheet(f"""
        QFrame#toastMessage {{
            background: {background};
            border: 1px solid {border};
            border-radius: 10px;
        }}
        QLabel {{
            color: {color};
            font-size: 14px;
            font-weight: 700;
            background: transparent;
        }}
    """)
    toast_layout = QHBoxLayout(toast)
    toast_layout.setContentsMargins(16, 11, 16, 11)
    label = QLabel(message)
    label.setWordWrap(True)
    label.setMaximumWidth(460)
    toast_layout.addWidget(label)
    toast.adjustSize()

    active = [item for item in getattr(host, "_active_toasts", []) if item.isVisible()]
    host._active_toasts = active + [toast]
    margin = 24
    y = margin + sum(item.height() + 8 for item in active)
    toast.move(max(margin, host.width() - toast.width() - margin), y)
    toast.show()
    toast.raise_()

    def close_toast():
        toast.hide()
        toast.deleteLater()
        host._active_toasts = [item for item in getattr(host, "_active_toasts", []) if item is not toast]

    QTimer.singleShot(duration, close_toast)


def configure_date_edit(edit):
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
    edit.setMinimumDate(QDate(2000, 1, 1))
    edit.setMaximumDate(QDate(2100, 12, 31))
    edit.setMinimumWidth(150)
    edit.setMaximumWidth(180)
    calendar = edit.calendarWidget()
    palette = calendar.palette()
    palette.setColor(QPalette.Window, QColor("#ffffff"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#24344f"))
    palette.setColor(QPalette.WindowText, QColor("#24344f"))
    palette.setColor(QPalette.ButtonText, QColor("#244783"))
    palette.setColor(QPalette.Highlight, QColor("#3f7dff"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    calendar.setPalette(palette)
    calendar.setAutoFillBackground(True)
    calendar.setStyleSheet(CALENDAR_STYLESHEET)
    calendar.setGridVisible(False)
    calendar.setFirstDayOfWeek(Qt.Monday)
    calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
    return edit

def make_page(title: str, subtitle: str = ""):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 28, 28, 28)
    layout.setSpacing(18)

    head = QHBoxLayout()
    title_box = QVBoxLayout()
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 28px; font-weight: 800; color: #0f1f3a;")
    title_box.addWidget(title_label)
    if subtitle:
        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("font-size: 14px; color: #627189; margin-top: 2px;")
        title_box.addWidget(sub_label)
    head.addLayout(title_box)
    head.addStretch()
    layout.addLayout(head)
    return page, layout, head

def make_button(text: str, primary: bool = False):
    btn = QPushButton(text)
    btn.setFixedHeight(38)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    if primary:
        btn.setStyleSheet("""
            QPushButton {
                background: #3f7dff;
                color: white;
                border: 1px solid #356fe3;
                border-radius: 10px;
                padding: 0 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #356fe3; }
            QPushButton:pressed { background: #2d63d4; }
        """)
    else:
        btn.setStyleSheet("""
            QPushButton {
                background: #edf4ff;
                color: #315dd3;
                border: 1px solid #d8e4fb;
                border-radius: 10px;
                padding: 0 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #e3edff; }
            QPushButton:pressed { background: #d7e5ff; }
        """)
    return btn

def make_panel(title: str):
    panel = QFrame()
    panel.setObjectName("panelFrame")
    panel.setStyleSheet("""
        QFrame#panelFrame {
            background: white;
            border: 1px solid #dfe8f5;
            border-radius: 16px;
        }
    """)
    outer_layout = QVBoxLayout(panel)
    outer_layout.setContentsMargins(18, 18, 18, 18)
    outer_layout.setSpacing(14)
    label = QLabel(title)
    label.setStyleSheet("font-size: 18px; font-weight: 800; color: #0f1f3a;")
    outer_layout.addWidget(label)
    content_layout = QVBoxLayout()
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(14)
    outer_layout.addLayout(content_layout)
    return panel, content_layout


def make_compact_form(fields, columns: int = 2, field_width: int = 340):
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(10)
    for index, (label_text, widget) in enumerate(fields):
        row = index // columns
        group = index % columns
        label_column = group * 2
        field_column = label_column + 1
        label = QLabel(label_text)
        label.setMinimumWidth(72)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        widget.setMaximumWidth(min(widget.maximumWidth(), field_width))
        grid.addWidget(label, row, label_column)
        grid.addWidget(widget, row, field_column)
        grid.setColumnStretch(field_column, 1)
    return grid

def make_table(headers, rows):
    table = ManagedTableWidget()
    table.setUpdatesEnabled(False)
    table.setColumnCount(len(headers))
    table.setRowCount(len(rows))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectItems)
    table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    table.setFocusPolicy(Qt.StrongFocus)
    table.setTabKeyNavigation(False)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setMouseTracking(True)
    table.setTextElideMode(Qt.ElideNone)
    table.setSortingEnabled(False)
    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    table.setMinimumHeight(150)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    header = table.horizontalHeader()
    header.setFixedHeight(44)
    header.setMinimumSectionSize(72)
    header.setSectionResizeMode(QHeaderView.Interactive)
    # Fill spare width on shorter tables while preserving horizontal scrolling on wide tables.
    header.setStretchLastSection(True)
    table.setStyleSheet("""
        QTableWidget { font-size: 13px; }
        QTableWidget::item { padding: 6px 8px; }
    """)
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            item = QTableWidgetItem(str(value) if value is not None else "")
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_index, col_index, item)
    # Keep columns readable. Wide tables can scroll horizontally instead of squeezing text.
    for column in range(len(headers)):
        header_width = max(96, len(str(headers[column])) * 18 + 26)
        content_width = max(
            (len(str(table.item(row, column).text())) * 8 + 28 for row in range(table.rowCount())),
            default=0,
        )
        table.setColumnWidth(column, min(260, max(72, header_width, content_width)))
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        table.setColumnWidth(column, min(260, max(table.columnWidth(column), 72)))
    header.setSectionResizeMode(QHeaderView.Interactive)
    table.verticalHeader().setDefaultSectionSize(42)
    for row in range(table.rowCount()):
        table.setRowHeight(row, 42)
    table.setSortingEnabled(True)
    table.setUpdatesEnabled(True)
    table.viewport().update()
    return table

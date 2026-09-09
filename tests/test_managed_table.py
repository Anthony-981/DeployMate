import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit

from src.ui.widgets.common import PasswordCellWidget, PasswordLineEdit, add_table_actions, filter_table, make_table


def run():
    app = QApplication.instance() or QApplication([])
    edited_ids = []
    deleted_ids = []
    rows = [
        [1, "", "训练节点", "10.6.90.3", "192.168.33.11", "A800"],
        [2, "", "推理节点", "10.6.90.8", "192.168.33.23", "910B4"],
        [3, "", "管理节点", "10.6.90.2", "192.168.33.10", "无"],
    ]
    table = make_table(["ID", "操作", "角色", "管理网IP", "集群网IP", "GPU型号"], rows)
    table.setColumnHidden(0, True)
    add_table_actions(table, [1, 2, 3], edited_ids.append, deleted_ids.append)
    table.resize(640, 300)
    table.show()
    app.processEvents()

    cell_position = table.visualRect(table.model().index(0, 2)).center()
    help_event = QHelpEvent(
        QEvent.ToolTip,
        cell_position,
        table.viewport().mapToGlobal(cell_position),
    )
    assert table.viewportEvent(help_event)
    app.processEvents()
    tooltip = table._light_tooltip
    assert tooltip is not None and tooltip.isVisible()
    assert tooltip.text() == "训练节点"
    assert "background-color: #ffffff" in tooltip.styleSheet()
    assert table.item(0, 2).toolTip() == ""
    assert all(
        table.item(row, column).textAlignment() & Qt.AlignHCenter
        and table.item(row, column).textAlignment() & Qt.AlignVCenter
        for row in range(table.rowCount())
        for column in range(table.columnCount())
        if table.item(row, column) is not None
    )
    tooltip_image = tooltip.grab().toImage()
    black_pixels = sum(
        1
        for y in range(tooltip_image.height())
        for x in range(tooltip_image.width())
        if tooltip_image.pixelColor(x, y).red() < 10
        and tooltip_image.pixelColor(x, y).green() < 10
        and tooltip_image.pixelColor(x, y).blue() < 10
    )
    assert black_pixels < tooltip_image.width() * tooltip_image.height() * 0.05
    table._hide_light_tooltip()

    password = PasswordLineEdit("secret")
    assert password.echoMode() == QLineEdit.Normal
    assert password.text() == "secret"
    password.toggle_button.click()
    assert password.echoMode() == QLineEdit.Password
    assert password.toggle_button.text() == "显示"
    password.toggle_button.click()
    assert password.echoMode() == QLineEdit.Normal
    assert password.toggle_button.text() == "隐藏"

    cell_password = PasswordCellWidget("admin@2025")
    assert cell_password.value_label.text() == "admin@2025"
    cell_password.toggle_button.click()
    assert cell_password.value_label.text() == "******"
    assert cell_password.toggle_button.text() == "显示"
    cell_password.toggle_button.click()
    assert cell_password.value_label.text() == "admin@2025"
    assert cell_password.toggle_button.text() == "隐藏"

    pinned = table.pinned_actions
    assert pinned is not None and pinned.isVisible()
    assert table.isColumnHidden(1)
    assert pinned.geometry().right() >= table.width() - 4
    assert pinned.horizontalHeaderItem(0).text() == "操作"
    assert pinned.horizontalHeaderItem(0).textAlignment() & Qt.AlignHCenter
    assert pinned.horizontalHeaderItem(0).textAlignment() & Qt.AlignVCenter
    assert table.action_header_label.text() == "操作"
    assert table.action_header_label.isVisible()
    assert table.action_header_label.alignment() & Qt.AlignHCenter
    assert table.action_header_label.alignment() & Qt.AlignVCenter
    assert table.action_header_label.geometry().width() == table.PINNED_WIDTH
    assert table.action_header_label.geometry().height() == table.horizontalHeader().height()
    assert pinned.horizontalHeader().height() == table.horizontalHeader().height() == 44
    main_rows_y = table.viewport().mapToGlobal(QPoint(0, 0)).y()
    pinned_rows_y = pinned.viewport().mapToGlobal(QPoint(0, 0)).y()
    assert pinned_rows_y == main_rows_y, (pinned_rows_y, main_rows_y)
    assert table.horizontalHeader().stretchLastSection()
    last_visible_column = table.columnCount() - 1
    last_column_right = (
        table.horizontalHeader().sectionViewportPosition(last_visible_column)
        + table.columnWidth(last_visible_column)
    )
    assert abs(last_column_right - table.viewport().width()) <= 1
    header_image = table.action_header_label.grab().toImage()
    dark_pixels = sum(
        1
        for y in range(header_image.height())
        for x in range(header_image.width())
        if header_image.pixelColor(x, y).red() < 110
        and header_image.pixelColor(x, y).green() < 130
        and header_image.pixelColor(x, y).blue() < 150
    )
    assert dark_pixels > 10, dark_pixels
    action_cell = pinned.cellWidget(0, 0)
    buttons = action_cell.findChildren(QPushButton)
    left = min(button.geometry().left() for button in buttons)
    right = max(button.geometry().right() for button in buttons)
    top = min(button.geometry().top() for button in buttons)
    bottom = max(button.geometry().bottom() for button in buttons)
    assert abs(((left + right) / 2) - (action_cell.width() / 2)) <= 1
    assert abs(((top + bottom) / 2) - (action_cell.height() / 2)) <= 1
    for row in range(table.rowCount()):
        main_rect = table.visualRect(table.model().index(row, 2))
        pinned_rect = pinned.visualRect(pinned.model().index(row, 0))
        assert main_rect.top() == pinned_rect.top()
        assert main_rect.bottom() == pinned_rect.bottom()
    for button in buttons:
        assert button.height() == 30, button.geometry()

    pinned_x = pinned.x()
    table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
    app.processEvents()
    assert pinned.x() == pinned_x

    filter_table(table, "推理")
    app.processEvents()
    assert table.isRowHidden(0) and pinned.isRowHidden(0)
    assert not table.isRowHidden(1) and not pinned.isRowHidden(1)

    filter_table(table, "")
    table.sortItems(3, Qt.DescendingOrder)
    app.processEvents()
    visible_id = int(table.item(0, 0).text())
    buttons = pinned.cellWidget(0, 0).findChildren(QPushButton)
    buttons[0].click()
    assert edited_ids == [visible_id], (edited_ids, visible_id)

    table.close()
    print("OK")


if __name__ == "__main__":
    run()

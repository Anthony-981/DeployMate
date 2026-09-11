import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.widgets.common import PaginationBar


def test_pagination_has_stable_page_count_and_correct_last_page():
    app = QApplication.instance() or QApplication([])
    pager = PaginationBar(page_size=20)
    pager.set_total(652)
    assert pager.page_count == 33
    pager.set_page(33)
    assert pager.page == 33
    assert pager.next.isEnabled() is False
    assert pager.previous.isEnabled() is True
    pager.set_total(21)
    assert pager.page == 2
    assert pager.page_count == 2
    pager.reset()
    assert pager.page == 1
    assert "第 1 / 2 页" in pager.summary.text()

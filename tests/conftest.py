"""Keep Qt alive until all GUI fixtures and transferred clipboard data are gone."""
import importlib.util
import pytest


@pytest.fixture(scope='session', autouse=True)
def qt_session():
    if importlib.util.find_spec('PySide6') is None:
        yield
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    # This clipboard belongs to the isolated offscreen test application.
    # Let Qt destroy owned QMimeData before Python finalizes its wrappers.
    app.clipboard().clear()
    for window in app.topLevelWidgets():
        window.close()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

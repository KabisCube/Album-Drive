import os
import sys
import tempfile
import threading
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QTimer, qInstallMessageHandler, qWarning
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from runtime_errors import install_error_log


app = QApplication([])
previous_hook = sys.excepthook
previous_thread_hook = threading.excepthook
captured = []
qt_messages = []
previous_qt_handler = qInstallMessageHandler(lambda kind, context, message: qt_messages.append(message))
sys.excepthook = lambda kind, value, trace: captured.append(str(value))
threading.excepthook = lambda args: captured.append(str(args.exc_value))
with tempfile.TemporaryDirectory() as directory:
    logger = install_error_log(app, Path(directory))
    assert install_error_log(app, Path(directory)) is logger
    try:
        raise ValueError('diagnostic main-thread test')
    except ValueError:
        sys.excepthook(*sys.exc_info())
    def callback():
        raise RuntimeError('diagnostic Qt callback test')
    QTimer.singleShot(0, callback)
    try:
        QTest.qWait(10)
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    def worker():
        raise OSError('diagnostic worker test')
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    text = logger.path.read_text(encoding='utf-8')
    assert 'ValueError: diagnostic main-thread test' in text
    assert 'RuntimeError: diagnostic Qt callback test' in text
    assert 'OSError: diagnostic worker test' in text
    assert len(captured) == 3
    qWarning('FFmpeg log: Estimating duration from bitrate, this may be inaccurate')
    assert not qt_messages
    qWarning('diagnostic Qt warning')
    assert qt_messages == ['diagnostic Qt warning']
    text = logger.path.read_text(encoding='utf-8')
    assert 'INFO Qt [default] FFmpeg log: Estimating duration' in text
    assert 'WARNING Qt [default] diagnostic Qt warning' in text
    assert (Path(directory) / 'crash.log').exists()
    logger.close()
    logger.close()
    qWarning('diagnostic restored handler')
    assert qt_messages[-1] == 'diagnostic restored handler'
qInstallMessageHandler(previous_qt_handler)
sys.excepthook = previous_hook
threading.excepthook = previous_thread_hook
print('PASS: persistent main-thread, Qt callback, worker and native-crash logging without losing existing hooks')

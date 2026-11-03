import faulthandler
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading

from app_paths import PROJECT_ROOT

from PySide6.QtCore import QStandardPaths, QtMsgType, qInstallMessageHandler, qVersion


class RuntimeErrorLog:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'errors.log'
        self.crash_file = (directory / 'crash.log').open('a', encoding='utf-8')
        try:
            self.handler = RotatingFileHandler(self.path, maxBytes=1024 * 1024, backupCount=2, encoding='utf-8')
        except OSError:
            self.crash_file.close()
            raise
        self.handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.logger = logging.getLogger('albumdrive.runtime')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.addHandler(self.handler)
        logging.getLogger().addHandler(self.handler)
        self.previous_hook = sys.excepthook
        self.previous_thread_hook = threading.excepthook
        sys.excepthook = self.handle_exception
        threading.excepthook = self.handle_thread_exception
        self.fault_handler_enabled = faulthandler.is_enabled()
        faulthandler.enable(self.crash_file, all_threads=True)
        self.closed = False
        self.previous_qt_handler = qInstallMessageHandler(self.handle_qt_message)
        self.logger.info('Started Python %s, Qt %s, executable %s', sys.version.split()[0], qVersion(), sys.executable)

    def handle_qt_message(self, kind, context, message):
        level = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
                 QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
                 QtMsgType.QtFatalMsg: logging.CRITICAL}.get(kind, logging.WARNING)
        estimate = message.strip('"\n ') == 'FFmpeg log: Estimating duration from bitrate, this may be inaccurate'
        self.logger.log(logging.INFO if estimate else level, 'Qt [%s] %s', context.category, message)
        if estimate:
            return
        if self.previous_qt_handler is not None:
            self.previous_qt_handler(kind, context, message)
        elif level >= logging.WARNING and sys.stderr is not None:
            sys.stderr.write(message + '\n')

    def handle_exception(self, kind, value, traceback):
        self.logger.error('Unhandled Python exception', exc_info=(kind, value, traceback))
        if sys.stderr is not None:
            self.previous_hook(kind, value, traceback)

    def handle_thread_exception(self, args):
        self.logger.error('Unhandled worker exception', exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        if sys.stderr is not None:
            self.previous_thread_hook(args)

    def close(self):
        if self.closed:
            return
        self.closed = True
        qInstallMessageHandler(self.previous_qt_handler)
        sys.excepthook = self.previous_hook
        threading.excepthook = self.previous_thread_hook
        faulthandler.disable()
        self.crash_file.close()
        if self.fault_handler_enabled and sys.stderr is not None:
            faulthandler.enable()
        logging.getLogger().removeHandler(self.handler)
        self.logger.removeHandler(self.handler)
        self.handler.close()


def install_error_log(app, directory=None):
    existing = getattr(app, '_runtime_error_log', None)
    if existing is not None and not existing.closed:
        return existing
    target = Path(directory) if directory is not None else PROJECT_ROOT / 'logs'
    try:
        logger = RuntimeErrorLog(target)
    except OSError:
        if directory is not None:
            raise
        target = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / 'logs'
        try:
            logger = RuntimeErrorLog(target)
        except OSError as error:
            logging.warning('Error logging unavailable: %s', error)
            return None
    app._runtime_error_log = logger
    return app._runtime_error_log

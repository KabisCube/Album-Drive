import shlex
import unittest
from scripts.build_android import order_qt_libraries


class AndroidBuildTests(unittest.TestCase):
    def test_qt_core_initializes_before_multimedia(self):
        arguments = '--qt-libs=Multimedia,Widgets,Core,Gui,Network,Concurrent --load-local-libs=platform --init-classes='
        result = shlex.split(order_qt_libraries(arguments))
        self.assertEqual(result[0], '--qt-libs=Core,Concurrent,Network,Gui,Widgets,Multimedia')
        self.assertEqual(result[1:], ['--load-local-libs=platform', '--init-classes='])

    def test_library_order_is_stable(self):
        first = order_qt_libraries('--qt-libs=Gui,Multimedia,Core,Widgets')
        second = order_qt_libraries('--qt-libs=Widgets,Core,Gui,Multimedia')
        self.assertEqual(first, second)

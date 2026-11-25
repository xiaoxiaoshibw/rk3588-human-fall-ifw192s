"""Actual QML slider/timer regression on the installed PySide Qt runtime.

The production Qt 6.5 native tour is run separately. This small harness extracts
the production controls/functions; the bridge records commands without data IO.
"""
from pathlib import Path
import unittest

from PySide6.QtCore import QPoint, Qt, QObject, QUrl, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest


class SeekQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        source = (Path(__file__).parent/'native/Main.qml').read_text(encoding='utf8')
        commands = source[source.index('    function send(op)'):source.index('    function urlToPath')]
        start = source.index('                Slider {\n                    id: seek;')
        end = source.index('                Label {', start)
        slider = source[start:end].replace('Layout.fillWidth: true', 'x: 50; y: 50; width: 400')
        qml = '''import QtQuick
import QtQuick.Controls
Window {
    id: root; width: 500; height: 140; visible: true
    property var snap: ({mode:"replay", sessionId:"A", generation:0, frameIndex:0, frameCount:500})
    property var recorded: []
    QtObject { id: viewer; function command(op) { root.recorded = root.recorded.concat([op]) } }
''' + commands + slider + '\n}'
        self.engine = QQmlApplicationEngine()
        self.errors = []
        self.engine.warnings.connect(lambda errors: self.errors.extend(str(e) for e in errors))
        self.engine.loadData(qml.encode(), QUrl('file:///seek-harness.qml'))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.slider = self.window.findChild(QObject, 'seekSlider')
        QTest.qWait(80)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        self.app.processEvents()
        self.assertEqual(self.errors, [])

    def commands(self):
        return self.window.property('recorded').toVariant()

    def test_drag_is_bounded_and_release_commits_last_position(self):
        y = 50 + int(self.slider.property('height')/2)
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(58, y))
        for x in range(70, 430, 3):
            QTest.mouseMove(self.window, QPoint(x, y), 0)
        self.assertTrue(self.slider.property('pressed'))
        expected = round(self.slider.property('value'))
        # A delayed bridge frame must not pull the handle backwards mid-drag.
        self.window.setProperty('snap', dict(mode='replay', sessionId='A', generation=1,
                                            frameIndex=12, frameCount=500))
        self.assertEqual(round(self.slider.property('value')), expected)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(427, y))
        QTest.qWait(80)
        sent = self.commands()
        self.assertTrue(sent)
        self.assertEqual(sent[-1]['index'], expected)
        self.assertLess(len(sent), 30, '120 pointer moves should be coalesced')
        self.assertEqual(self.window.property('pendingSeekIndex'), -1)
        print('Qt %s: 120 moves -> %d commands, final=%d' % (qVersion(), len(sent), expected))

    def test_context_change_cancels_real_timer(self):
        y = 50 + int(self.slider.property('height')/2)
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(58, y))
        QTest.mouseMove(self.window, QPoint(300, y), 0)
        before = len(self.commands())
        self.window.setProperty('snap', dict(mode='live', sessionId='B', generation=1,
                                            frameIndex=0, frameCount=500))
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(300, y))
        QTest.qWait(100)
        self.assertEqual(len(self.commands()), before)
        self.assertEqual(self.window.property('pendingSeekIndex'), -1)


if __name__ == '__main__':
    unittest.main()

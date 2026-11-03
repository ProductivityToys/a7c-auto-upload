"""Session-only desktop log presentation; entries remain plain text when copied."""
from datetime import datetime

from PySide6.QtGui import QColor, QFontDatabase, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class RuntimeLog(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('runtimeLog')
        self.setAccessibleName('运行日志')
        self.setReadOnly(True)
        self.setMaximumBlockCount(200)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFixedHeight(150)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.setFont(font)
        self.setStyleSheet(f'''
            QPlainTextEdit#runtimeLog {{
                background: #172333; color: #dbe5ef;
                border: 1px solid #26364b; border-radius: 6px; padding: 10px;
                font-family: "{font.family()}"; font-size: 11px;
                selection-background-color: #365477;
            }}
        ''')

    def append_entry(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        color = {'INFO': '#91b8e4', 'OK': '#89d5ae', 'ERROR': '#ffaaa5'}[level]
        scroll = self.verticalScrollBar()
        follow = scroll.value() >= scroll.maximum()
        previous = scroll.value()
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.End)
        for line in str(message).splitlines():
            if not self.document().isEmpty():
                cursor.insertBlock()
            for text, foreground in ((timestamp + '  ', '#8193aa'),
                                     (f'{level:<5} ', color),
                                     (line, '#ffb9b4' if level == 'ERROR' else '#dbe5ef')):
                style = QTextCharFormat()
                style.setForeground(QColor(foreground))
                cursor.insertText(text, style)
        scroll.setValue(scroll.maximum() if follow else previous)

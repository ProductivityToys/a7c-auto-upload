"""In-app installation, recovery and license help; no USB operations."""
from pathlib import PurePosixPath
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QTextBrowser, QDialogButtonBox
from .documentation import GUIDES, read_guide


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('A7C 自动上传 · 使用说明')
        self.resize(760, 680)
        layout = QVBoxLayout(self)
        self.topics = QComboBox()
        for title, name in GUIDES.items():
            self.topics.addItem(title, name)
        layout.addWidget(self.topics)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.open_link)
        layout.addWidget(self.browser, 1)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.topics.currentIndexChanged.connect(self.load_topic)
        self.load_topic()

    def load_topic(self, *_):
        self.browser.setMarkdown(read_guide(self.topics.currentData()))
        self.browser.moveCursor(self.browser.textCursor().MoveOperation.Start)

    def open_link(self, url):
        if url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)
            return
        if url.scheme():
            return
        if url.path():
            name = PurePosixPath(url.path()).name
            index = self.topics.findData(name)
            if index < 0:
                return
            self.topics.setCurrentIndex(index)
        if url.fragment():
            self.browser.scrollToAnchor(url.fragment())

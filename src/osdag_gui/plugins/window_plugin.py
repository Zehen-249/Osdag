from PySide6.QtWidgets import (
    QApplication, 
    QDialog, 
    QVBoxLayout, 
    QPushButton, 
    QHBoxLayout, 
    QWidget, 
    QMainWindow,
    QSizePolicy, 
    QLabel,
    QTextEdit,
    QScrollArea
)
from osdag_gui.plugins.plugin_base import PluginBase

class WindowPlugin(PluginBase, QMainWindow):
    """Plugin that provides a Window."""

    def setupUI(self) -> None:
        """Setup UI of the Window."""
        super().setupUI()
        self.window = QMainWindow()

        return
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
from osdag_gui.plugin.plugin_base import PluginBase

class WindowPlugin(PluginBase, QMainWindow):
    """Plugin that provides a Window."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def open(self,key:str, name:str, parent:QApplication) -> None:
        """Implement the open method to display the plugin's window.
        Args:
            key (str): The unique key for the plugin.
            name (str): The display name of the plugin.
            parent (QApplication): The parent application to attach this plugin's window to.
        """
        raise NotImplementedError("Subclasses must implement the open() method.")

from abc import abstractmethod
from PySide6.QtWidgets import (
    QVBoxLayout,  
    QWidget, 
    QLabel,
)
from osdag_gui.plugin.plugin_base import PluginBase

class WidgetPlugin(PluginBase, QWidget):
    """Base class for widget-based plugins."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)

    def open(self, key: str, name: str, parent: QWidget) -> None:
        """Implement the open method to display the plugin's widget.
        Args:
            key (str): The unique key for the plugin.
            name (str): The display name of the plugin.
            parent (QWidget): The parent widget to attach this plugin's widget to.
        """
        raise NotImplementedError("Subclasses must implement the open() method.")
        
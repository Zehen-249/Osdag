from PySide6.QtWidgets import (
    QWidget,
    QApplication
)

class PluginBase:
    """Base class for all Osdag plugins."""
    def __init__(self, *args, **kwargs) -> None:
        pass

    def open(self, key: str, name: str, parent: QWidget | QApplication) -> None:
        """Open the plugin. Override in subclass.
        Args:
            key (str): The unique key for the plugin.
            name (str): The display name of the plugin.
            parent (QWidget | QApplication): The parent widget or application to attach this plugin to.
        """
        raise NotImplementedError("Subclasses must implement the open() method.")
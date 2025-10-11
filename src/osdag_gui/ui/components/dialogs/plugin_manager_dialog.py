from pathlib import Path
import sys, shutil, json, site
import importlib
import importlib.metadata as metadata
import pkgutil
from dataclasses import dataclass, field
from PySide6.QtWidgets import (
    QApplication, 
    QDialog, 
    QVBoxLayout, 
    QPushButton, 
    QHBoxLayout, 
    QWidget, 
    QSizePolicy, 
    QLabel,
    QTextEdit,
    QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QIcon
from osdag_gui.ui.components.dialogs.custom_titlebar import CustomTitleBar
from osdag_gui.data.ui_data import Data

active_plugins = Data.MODULES["Add-Ons"]
@dataclass
class PluginMetaData:      
    name: str
    description: str = field(default_factory=lambda: "No description available.")
    authors: list = field(default_factory=lambda: [{"name": "Unknown"}])
    version: str = field(default_factory=lambda: "1.0.0")
    status: str = field(default_factory=lambda: "Inactive")
    module: object = field(default=None)
    entry_class: object = field(default=None)

class StatusIndicator(QWidget):
    def __init__(self, status="Inactive"):
        super().__init__()
        self.status = status
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        layout.setSpacing(5)

        self.circle = QLabel()
        self.circle.setFixedSize(12, 12)
        self.circle.setStyleSheet("border-radius: 6px; background-color: red;")

        self.text = QLabel(status)
        self.text.setStyleSheet("font-size: 12pt; font-weight: bold; color: #444;")

        layout.addWidget(self.circle)
        layout.addWidget(self.text)

        self.update_status(status)

    def update_status(self, status: str):
        self.status = status
        if status == "Active":
            self.circle.setStyleSheet("border-radius: 6px; background-color: green;")
            self.text.setText("Active")
            self.text.setStyleSheet("font-size: 9pt; font-weight: bold; color: green;")
        else:
            self.circle.setStyleSheet("border-radius: 6px; background-color: red;")
            self.text.setText("Inactive")
            self.text.setStyleSheet("font-size: 9pt; font-weight: bold; color: red;")

class PluginWidget(QWidget):
    def __init__(self, plugin: PluginMetaData):
        super().__init__()
        self.plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
    
        self.setStyleSheet("""
            PluginWidget {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                background-color: #ffffff;
            }
        """)

        # --- HEADER ROW ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(5)

        self.name_label = QLabel(plugin.name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #90AF13;")

        self.status_indicator = StatusIndicator(plugin.status)

        header_layout.addWidget(self.name_label, alignment=Qt.AlignLeft)
        header_layout.addStretch()
        header_layout.addWidget(self.status_indicator, alignment=Qt.AlignRight)

        layout.addWidget(header)

        # --- CONTENT ROW ---
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)

        # LEFT SIDE (description)
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setText(plugin.description)
        self.content.setFixedHeight(100)
        self.content.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-size: 9.5pt;
                color: #444;
                background: #fafafa;
            }
        """)
        content_layout.addWidget(self.content, stretch=3)
 


       # RIGHT SIDE (buttons)
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(4, 4, 4, 4)
        btn_layout.setSpacing(10)
        btn_layout.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.btnActivate = QPushButton("Activate")
        self.btnDeactivate = QPushButton("Deactivate")
        self.btnRemove = QPushButton("Remove")

        for btn in (self.btnActivate, self.btnDeactivate, self.btnRemove):
            btn.setMinimumHeight(30)
            btn.setMinimumWidth(100)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #90AF13;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 9pt;
                    font-weight: bold;
                    margin: 4px;
                }
                QPushButton:hover { background-color: #7A9611; }
                QPushButton:pressed { background-color: #6B850F; }
            """)
            btn_layout.addWidget(btn, 0, Qt.AlignRight) 

        content_layout.addLayout(btn_layout, stretch=1)

        layout.addWidget(content)

        # --- Button Callbacks ---
        self.btnActivate.clicked.connect(lambda checked=False: self.on_activate(plugin))
        self.btnDeactivate.clicked.connect(lambda checked=False: self.on_deactivate(plugin))
        self.btnRemove.clicked.connect(lambda checked=False: self.on_remove(plugin))

        content_min_width = self.content.sizeHint().width() + 150 
        self.setMinimumWidth(content_min_width)

    def on_activate(self, plugin:PluginMetaData):
        active_plugins.append((f"{self.plugin.name}" ,":/vectors/IITB_logo.svg"))
        self.plugin.status = "Active"
        self.status_indicator.update_status(self.plugin.status)

    def on_deactivate(self, plugin:PluginMetaData):
        active_plugins[:] = [
            p for p in active_plugins if p[0] != self.plugin.name
        ]
        self.plugin.status = "Inactive"
        self.status_indicator.update_status(self.plugin.status)

    def on_remove(self):
        self.setParent(None)
        self.deleteLater()


class PluginManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("PluginManagerDialog")
        self.setWindowIcon(QIcon(":/images/osdag_logo.png"))
        self.setFixedSize(720, 600)

        # Layout and style
        self.setStyleSheet("""
            QDialog#PluginManagerDialog { background-color: #ffffff; border: 1px solid #90AF13; }
            QWidget#ContentWidget { background-color: #ffffff; }
            QPushButton { background-color: #90AF13; color: white; border: none; border-radius: 5px;
                          padding: 5px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #7A9611; }
            QPushButton:pressed { background-color: #6B850F; }
        """)

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(1, 1, 1, 1)
        mainLayout.setSpacing(0)

        # Title bar
        self.titleBar = CustomTitleBar()
        self.titleBar.setTitle("Plugin Manager")
        mainLayout.addWidget(self.titleBar)

        # Content
        contentWidget = QWidget(self)
        contentWidget.setObjectName("ContentWidget")
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(10, 10, 10, 10)
        contentLayout.setSpacing(10)

        # Logo
        self.logoLabel = QSvgWidget(":/vectors/Osdag.svg", self)
        self.logoLabel.setFixedSize(325, 85)
        self.logoLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        contentLayout.addWidget(self.logoLabel, 0, Qt.AlignLeft)

        # Scroll area for plugins
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 0.5px solid black; background-color: #F0F0F0; }")
        contentLayout.addWidget(scroll)

        # Container for plugin widgets
        self.pluginContainer = QWidget()
        self.pluginLayout = QVBoxLayout(self.pluginContainer)
        self.pluginLayout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.pluginContainer)

        # Add plugins
        plugins = self._load_installed_plugins()
        print(plugins)
        for plugin in plugins:
            pw = PluginWidget(plugin)
            pw.setFixedHeight(120)
            pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.pluginLayout.addWidget(pw)

        # OK button
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        self.okButton = QPushButton("OK", self)
        self.okButton.setFixedHeight(30)
        self.okButton.setStyleSheet("""
            QPushButton { background-color: #90AF13; color: white; border: none; border-radius: 5px;
                           padding: 5px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #7A9611; }
            QPushButton:pressed { background-color: #6B850F; }
        """)
        self.okButton.clicked.connect(self.accept)
        buttonLayout.addWidget(self.okButton)

        contentLayout.addLayout(buttonLayout)
        mainLayout.addWidget(contentWidget)



    def _load_installed_plugins(self) -> list[PluginMetaData]:
        plugins: list[PluginMetaData] = []
        development_plugins_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "plugins"
        try:
            entry_points = metadata.entry_points().select(group="osdag.plugins")
            print(entry_points)
            for ep in entry_points:
                module = ep.load()
                print(f"Loaded module: {module}")
                if not getattr(module, "IS_OSDAG_PLUGIN", False):
                    print(f"[WARN] Module {ep.name} is not marked as an Osdag plugin.")
                    continue
                meta = getattr(module, "META", {})
                name = meta.get("name")
                if name is None:
                    print(f"[WARN] Plugin {ep.name} missing 'name' in META.")
                    continue
                description = meta.get("description", "No description available.")
                authors = meta.get("authors", [{"name": "Unknown"}])
                version = meta.get("version", "1.0")
                entry_class = self._resolve_entry_class(module, name, getattr(module, "ENTRY_POINT", None))
                print(entry_class)
                if entry_class is None:
                    print(f"[WARN] Failed to resolve entry class for plugin '{name}' (site-packages).")
                    continue
                plugins.append(
                    PluginMetaData(
                        name=name,
                        description=description,
                        authors=authors,
                        version=version,
                        module=module,
                        entry_class=entry_class,
                    )
                )
        except Exception as e:
            print(f"[WARN] Entry point loading failed: {e}")

        if development_plugins_path.exists():
            for _, name, ispkg in pkgutil.iter_modules([str(development_plugins_path)]):
                existing_names = {p.name for p in plugins}
                if name in existing_names:
                    continue
                if not ispkg:
                    continue
                try:
                    module = importlib.import_module(f"plugins.{name}")
                    if not getattr(module, "IS_OSDAG_PLUGIN", False):
                        continue
                    
                    meta = getattr(module, "META", {})
                    name = meta.get("name")
                    if name is None:
                        print(f"[WARN] Plugin {ep.name} in development missing 'name' in META.")
                        continue
                    description = meta.get("description", "No description available.")
                    authors = meta.get("authors", [{"name": "Unknown"}])
                    version = meta.get("version", "1.0")
                    entry_class = self._resolve_entry_class(module, name, getattr(module, "ENTRY_POINT", None))
                    if entry_class is None:
                        print(f"[WARN] Failed to resolve entry class for plugin '{name}' (development).")
                        continue

                    plugins.append(
                        PluginMetaData(
                            name=name,
                            description=description,
                            authors=authors,
                            version=version,
                            module=module,
                            entry_class=entry_class,
                        )
                    )
                except Exception as e:
                    print(f"[WARN] Skipped {name}: {e}")
        print(plugins)
        return plugins
    
    def _resolve_entry_class(self, module, name, entry_path: str):

        if not entry_path:
            print(f"[WARN] Plugin '{name}' missing 'PLUGIN_ENTRY'.")
            return None


        try:
            parts = entry_path.split(".")
            submodule_name = ".".join(parts[:-1])
            class_name = parts[-1]
            entry_module = importlib.import_module(f"{module.__name__}.{submodule_name}")
            entry_class = getattr(entry_module, class_name)
            return entry_class

        except Exception as e:
            print(f"[WARN] Could not resolve entry class '{entry_path}' for plugin '{name}': {e}")
            return None

# Test the dialog
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = PluginManagerDialog()
    dialog.exec()
    sys.exit(app.exec())
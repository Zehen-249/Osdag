from pathlib import Path

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
    QScrollArea,
    QListWidget,
    QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QFont, QIcon
from osdag_gui.ui.components.dialogs.custom_titlebar import CustomTitleBar
from osdag_gui.data.ui_data import Data
from osdag_core.utils.plugin_manager import PluginManager, PluginMetaData
from osdag_gui.ui.components.dialogs.plugin_store_dialog import PluginStoreDialog
from osdag_gui.ui.components.dialogs.custom_messagebox import CustomMessageBox, MessageBoxType

class PluginWidget(QWidget):
    activate = Signal(PluginMetaData)
    deactivate = Signal(PluginMetaData)

    def __init__(self, plugin: PluginMetaData, parent=None):
        super().__init__(parent)
        self.setObjectName("PluginWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.setStyleSheet("""
            QWidget#PluginWidget {
                background-color: #ffffff;
                border: 2px solid #c8c8c8;
                border-radius: 6px;
            }
        """)

        # --- HEADER ROW ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(5)

        self.name_label = QLabel(
            f"{'<b>'+plugin.name.title()+' v'+str(plugin.version)+'</b> (Dev Plugin)' if plugin.is_dev else '<b>'+plugin.name.title()+' v'+str(plugin.version)+'</b>'}")
        self.name_label.setStyleSheet(
            "font-weight: bold; font-size: 12pt; color: #90AF13;")

        # Status indicator
        self.status_layout = QHBoxLayout()
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(6)

        self.status_circle = QLabel()
        self.status_circle.setFixedSize(12, 12)

        self.status_text = QLabel()
        self.status_text.setStyleSheet(
            "font-size: 9pt; font-weight: bold;"
        )

        self.status_layout.addWidget(self.status_circle)
        self.status_layout.addWidget(self.status_text)

        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        header_layout.addLayout(self.status_layout)

        layout.addWidget(header)

        # --- CONTENT ROW ---
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)

        # LEFT SIDE (description)
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        content_text = f"{'<b>Author</b>' if len(self.plugin.authors) == 1 else '<b>Authors</b>'}: ({', '.join(author.title() for author in self.plugin.authors)})"
        content_text += f"<br><b>Description</b>: {self.plugin.description}"
        self.content.setText(content_text)
        self.content.setMinimumHeight(70)
        self.content.setMaximumHeight(120)
        self.content.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
                font-size: 9.5pt;
                color: #444444;
                background: #FAFAFA;
            }
        """)
        content_layout.addWidget(self.content, stretch=3)

        # -------------------------
        # Buttons
        # -------------------------
        self.btnActivate = QPushButton("Activate")
        self.btnDeactivate = QPushButton("Deactivate")

        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        for btn in (
            self.btnActivate,
            self.btnDeactivate
        ):
            btn.setFixedSize(100, 30)

            btn.setStyleSheet("""
                QPushButton {
                    background-color: #90AF13;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 9pt;
                    font-weight: bold;
                }

                QPushButton:hover {
                    background-color: #7A9611;
                }

                QPushButton:pressed {
                    background-color: #6B850F;
                }

                QPushButton:disabled {
                    background-color: #B8C58A;
                    color: #F5F5F5;
                }
            """)

            btn_layout.addWidget(btn)

        btn_layout.addStretch()

        self.set_status(plugin.status)
        content_layout.addLayout(btn_layout)

        layout.addWidget(content)

        # --- Button Callbacks ---
        self.btnActivate.clicked.connect(self._emit_activate)
        self.btnDeactivate.clicked.connect(self._emit_deactivate)

        content_min_width = self.content.sizeHint().width() + 150
        self.setMinimumWidth(content_min_width)

    def set_status(self, status: bool) -> None:
        """Update status indicator and action button visibility."""

        if status:
            self.status_circle.setStyleSheet("""
                background-color: #008000;
                border-radius: 6px;
            """)

            self.status_text.setText("Activated")
            self.status_text.setStyleSheet("""
                color: #008000;
                font-size: 9pt;
                font-weight: bold;
            """)

            self.btnActivate.hide()
            self.btnDeactivate.show()

        else:
            self.status_circle.setStyleSheet("""
                background-color: #C62828;
                border-radius: 6px;
            """)

            self.status_text.setText("Deactivated")
            self.status_text.setStyleSheet("""
                color: #C62828;
                font-size: 9pt;
                font-weight: bold;
            """)

            self.btnActivate.show()
            self.btnDeactivate.hide()


    def _emit_activate(self):
        if not self.plugin.status:
            self.plugin.status = not self.plugin.status
            self.set_status(self.plugin.status)
            self.activate.emit(self.plugin)

    def _emit_deactivate(self):
        if self.plugin.status:
            self.plugin.status = not self.plugin.status
            self.set_status(self.plugin.status)
            self.deactivate.emit(self.plugin)



class PluginManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_manager: PluginManager = QApplication.instance().plugin_manager
        self.plugins: list[PluginMetaData] = self.plugin_manager.discover_local_plugins(
        )
        self.data_modules = Data.MODULES
        self.data_navbar_icons = Data.NAVBAR_ICONS
        self.active_plugins: dict = Data.PLUGINS
        self.app = QApplication.instance()
        self.main_window = self.app.main_window

        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("PluginManagerDialog")
        self.setWindowIcon(QIcon(":/images/osdag_logo.png"))

        # Size dialog relative to parent window
        if parent is not None:
            parent_size = parent.size()

            width = int(parent_size.width() * 0.80)
            height = int(parent_size.height() * 0.80)

            self.resize(width, height)

            self.setMinimumSize(
                min(800, parent_size.width()),
                min(600, parent_size.height())
            )

            # Center over parent
            parent_geometry = parent.frameGeometry()
            self.move(
                parent_geometry.center()
                - self.rect().center()
            )
        else:
            self.resize(1000, 700)
            self.setMinimumSize(800, 600)

        # Layout and style
        self.setStyleSheet("""
            QDialog#PluginManagerDialog {
                background-color: #ffffff;
                border: 2px solid #90AF13;
            }

            QWidget#ContentWidget {
                background-color: #ffffff;
            }

            QPushButton {
                background-color: #90AF13;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 20px;
                font-size: 12px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #7A9611;
            }

            QPushButton:pressed {
                background-color: #6B850F;
            }

            QPushButton:disabled {
                background-color: #B8C58A;
                color: #F5F5F5;
            }
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
        self.logoLabel = QSvgWidget(
            ":/vectors/Osdag_light.svg",
            self
        )

        logo_height = max(
            55,
            min(85, int(self.height() * 0.10))
        )

        svg_size = self.logoLabel.renderer().defaultSize()

        if not svg_size.isEmpty() and svg_size.height() > 0:
            logo_width = int(
                svg_size.width()
                * logo_height
                / svg_size.height()
            )

            self.logoLabel.setFixedSize(
                logo_width,
                logo_height
            )
        else:
            self.logoLabel.setFixedSize(
                500,
                logo_height
            )

        contentLayout.addWidget(
            self.logoLabel,
            0,
            Qt.AlignLeft
        )

        # Scroll area for plugins
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #F4F4F4;
            }

            QScrollArea > QWidget > QWidget {
                background: #F4F4F4;
            }

            /* Vertical scrollbar */
            QScrollBar:vertical {
                background: #F4F4F4;
                width: 8px;
                margin: 0px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #B8C58A;
                min-height: 35px;
                border-radius: 4px;
            }

            QScrollBar::handle:vertical:hover {
                background: #90AF13;
            }

            QScrollBar::handle:vertical:pressed {
                background: #7A9611;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }

            /* Horizontal scrollbar */
            QScrollBar:horizontal {
                background: #F4F4F4;
                height: 8px;
                border: none;
            }

            QScrollBar::handle:horizontal {
                background: #B8C58A;
                min-width: 35px;
                border-radius: 4px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #90AF13;
            }

            QScrollBar::handle:horizontal:pressed {
                background: #7A9611;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
                border: none;
            }

            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
        contentLayout.addWidget(scroll)

        # Container for plugin widgets
        self.pluginContainer = QWidget()
        self.pluginLayout = QVBoxLayout(self.pluginContainer)
        self.pluginLayout.setContentsMargins(10, 10, 10, 10)
        self.pluginLayout.setSpacing(12)
        self.pluginLayout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.pluginContainer)

        if len(self.plugins) > 0:
            print("\n===========Loaded Plugins===========\n")
            for plugin in self.plugins:
                print(
                    f"    {plugin.name} by {', '.join(author for author in plugin.authors)}")
                if plugin.status:
                    print("     [INFO] Status: Active")
                    self.activate_plugin(plugin)
                else:
                    print("     [INFO] Status: Inactive")
                pw = self.create_plugin_widget(plugin)
                self.pluginLayout.addWidget(pw)
            print("\n=====================================\n")

        # Plugin Store button
        self.storeButton = QPushButton("Store", self)
        self.storeButton.setFixedHeight(30)
        self.storeButton.setStyleSheet("""
            QPushButton {
                background-color: #90AF13;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 20px;
                font-size: 12px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #7A9611;
            }

            QPushButton:pressed {
                background-color: #6B850F;
            }
        """)
        self.storeButton.clicked.connect(self.open_store_dialog)

        #  Development Plugins Path add-on
        self.devPathsButton = QPushButton("Development Paths")
        self.devPathsButton.setFixedHeight(30)

        self.devPathsButton.clicked.connect(
            self.open_dev_paths_dialog
        )

        # OK button
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.storeButton)
        buttonLayout.addWidget(self.devPathsButton)
        buttonLayout.addStretch()
        self.okButton = QPushButton("OK", self)
        self.okButton.setFixedHeight(30)
        self.okButton.setStyleSheet("""
            QPushButton { background-color: #90AF13; color: white; border: none; border-radius: 5px;
                           padding: 5px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #7A9611; }
            QPushButton:pressed { background-color: #6B850F; }
        """)
        self.okButton.clicked.connect(self.okClicked)
        buttonLayout.addWidget(self.okButton)

        contentLayout.addLayout(buttonLayout)
        mainLayout.addWidget(contentWidget)

    def activate_plugin(self, plugin: PluginMetaData):
        plugin = self.plugin_manager.get_plugin(plugin.id)
        if plugin and plugin.name not in self.active_plugins.keys():
            self.active_plugins[plugin.name] = plugin.module_tree
            self.data_modules.update({plugin.name: plugin.module_tree})
            self.data_navbar_icons.update({plugin.name: plugin.icons})

    def deactivate_plugin(self, plugin: PluginMetaData):
        self.active_plugins.pop(plugin.name, None)
        self.data_modules.pop(plugin.name, None)
        self.data_navbar_icons.pop(plugin.name, None)


    def open_store_dialog(self):
        # print("[PLUGIN STORE] Opening Plugin Store Dialog...")
        store_dialog = PluginStoreDialog(parent=self)
        store_dialog.show()

    def open_dev_paths_dialog(self):

        self.dev_paths_dialog = DevelopmentPluginPathsDialog(
            self.plugin_manager,
            self
        )

        self.dev_paths_dialog.refresh_plugins.connect(self.refresh_plugins)
        self.dev_paths_dialog.show()

    def create_plugin_widget(self, plugin):
        pw = PluginWidget(plugin=plugin, parent=self)

        pw.activate.connect(self.plugin_manager.activate)
        pw.activate.connect(self.activate_plugin)

        pw.deactivate.connect(self.plugin_manager.deactivate)
        pw.deactivate.connect(self.deactivate_plugin)


        # IMPORTANT:
        # Let the widget determine its own required height.
        pw.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum
        )

        return pw

    def refresh_plugins(self):
        self.plugin_manager.dev_plugins_paths = self.plugin_manager.state_manager.get_plugin_paths()
        self.plugins = self.plugin_manager.discover_local_plugins()
        # Clear old plugin widgets
        for i in reversed(range(self.pluginLayout.count())):
            widget = self.pluginLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Re-add plugin widgets
        if len(self.plugins) > 0:
            for plugin in self.plugins:
                pw = self.create_plugin_widget(plugin)
                self.pluginLayout.addWidget(pw)

    def closeEvent(self, event):
        self.plugin_manager.state_manager.flush()
        super().closeEvent(event)

    def okClicked(self):
        self.plugin_manager.state_manager.flush()
        self.accept()


class DevelopmentPluginPathsDialog(QDialog):
    refresh_plugins = Signal()

    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)

        self.plugin_manager = plugin_manager

        # --------------------------------------------------
        # Window
        # --------------------------------------------------
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("DevelopmentPluginPathsDialog")
        self.setFixedSize(600, 400)

        self.setStyleSheet("""
            QDialog#DevelopmentPluginPathsDialog {
                background-color: white;
                border: 1px solid #90AF13;
            }

            QWidget#contentWidget {
                background-color: #F4F4F4;
            }

            QWidget#footer {
                background-color: white;
            }

            QLabel {
                color: #222222;
            }

            QListWidget {
                background-color: white;
                border: 1px solid #C8C8C8;
                border-radius: 3px;
                padding: 4px;
                font-size: 9pt;
            }

            QListWidget::item {
                padding: 4px;
            }

            QListWidget::item:selected {
                background-color: #90AF13;
                color: white;
            }

            QPushButton {
                background-color: #90AF13;
                color: white;
                border: none;
                border-radius: 5px;
                min-height: 30px;
                padding: 0 18px;
                font-size: 9pt;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #7A9611;
            }

            QPushButton:pressed {
                background-color: #6B850F;
            }
        """)

        # ==================================================
        # Main layout
        # ==================================================

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        # ==================================================
        # Title bar
        # ==================================================

        self.title_bar = CustomTitleBar()
        self.title_bar.setTitle("Development Plugin Repositories")

        main_layout.addWidget(self.title_bar)

        # ==================================================
        # Content area
        # ==================================================

        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # --------------------------------------------------
        # Heading
        # --------------------------------------------------

        label = QLabel("Configured Plugin Repository Locations")
        label.setStyleSheet("""
            font-size: 11pt;
            font-weight: bold;
            color: #222222;
        """)

        content_layout.addWidget(label)

        # --------------------------------------------------
        # Repository list
        # --------------------------------------------------

        self.path_list = QListWidget()
        self.path_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        content_layout.addWidget(self.path_list)

        # --------------------------------------------------
        # Repository buttons
        # --------------------------------------------------

        path_button_layout = QHBoxLayout()
        path_button_layout.setContentsMargins(0, 0, 0, 0)
        path_button_layout.setSpacing(6)

        self.add_button = QPushButton("Add Repository")
        self.remove_button = QPushButton("Remove Repository")

        path_button_layout.addWidget(self.add_button)
        path_button_layout.addWidget(self.remove_button)
        path_button_layout.addStretch()

        content_layout.addLayout(path_button_layout)

        main_layout.addWidget(content_widget)

        # ==================================================
        # Bottom footer
        # ==================================================

        footer = QWidget()
        footer.setObjectName("footer")
        footer.setFixedHeight(48)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 6)
        footer_layout.setSpacing(6)

        footer_layout.addStretch()

        self.close_button = QPushButton("Close")
        footer_layout.addWidget(self.close_button)

        main_layout.addWidget(footer)

        # ==================================================
        # Signals
        # ==================================================

        self.add_button.clicked.connect(self.add_repository)
        self.remove_button.clicked.connect(self.remove_repository)
        self.close_button.clicked.connect(self.accept)

        self.refresh_paths()

    def refresh_paths(self):

        self.path_list.clear()

        paths = self.plugin_manager.state_manager.get_plugin_paths()

        for path in paths:
            text = str(path)

            self.path_list.addItem(text)

    def add_repository(self):

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Development Plugin Repository"
        )

        if not directory:
            return

        self.plugin_manager.state_manager.add_plugin_path(
            directory
        )
        self.refresh_paths()
        self.refresh_plugins.emit()

    def remove_repository(self):

        item = self.path_list.currentItem()

        if item is None:
            CustomMessageBox(
                title="Please select a repository containing plugin init file.",
                text='No Selection',
                dialogType=MessageBoxType.Information
            ).exec()
            return

        path = item.text().split(" (")[0]

        reply = QMessageBox.question(
            self,
            "Remove Repository",
            f"Remove repository?\n\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.plugin_manager.state_manager.remove_plugin_path(
            path
        )

        self.refresh_paths()
        self.refresh_plugins.emit()

    def closeEvent(self, event):

        self.plugin_manager.state_manager.flush()

        super().closeEvent(event)

# # Test the dialog
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     dialog = PluginManagerDialog()
#     dialog.exec()
#     sys.exit(app.exec())

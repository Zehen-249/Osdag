from packaging import version
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
from PySide6.QtCore import Qt, Signal, Slot, QObject, QThread, QTimer, QMetaObject, QSize
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QIcon
from osdag_gui.ui.components.dialogs.custom_titlebar import CustomTitleBar
from osdag_core.utils.plugin_manager import PluginMetaData


class Worker(QObject):
    finished = Signal(bool, str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            success, error = result

            self.finished.emit(success, error or "")

        except Exception:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, "Worker execution failed")

class PluginWidget(QWidget):
    download = Signal(PluginMetaData)
    delete = Signal(PluginMetaData)
    update_plugin = Signal(PluginMetaData)

    def __init__(self, plugin: PluginMetaData, parent=None):
        super().__init__(parent)
        self.setObjectName("PluginWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.plugin = plugin

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )

        self.setStyleSheet("""
            QWidget#PluginWidget {
                background-color: #ffffff;
                border: 2px solid #c8c8c8;
                border-radius: 6px;
            }
        """)
        # ============================================================
        # HEADER
        # ============================================================

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(7)

        self.name_label = QLabel(f"{self.plugin.name.title()} v{str(self.plugin.version)}")
        self.name_label.setStyleSheet("""
            QLabel {
                font-size: 12pt;
                font-weight: bold;
                color: #90AF13;
            }
        """)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10pt;
                font-weight: normal;
                color: #90AF13;
            }
        """)

        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()

        layout.addWidget(header)


        # ============================================================
        # CONTENT
        # ============================================================

        content = QWidget()

        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(20)


        # -------------------------
        # Information
        # -------------------------

        self.content = QLabel()

        content_text = f"Download Size: {self.plugin.download_size} MB\n\n"

        self.content.setText(content_text)
        self.content.setWordWrap(True)
        self.content.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.content.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.content.setStyleSheet("""
            QLabel {
                font-size: 9.5pt;
                color: #444444;
                background: transparent;
                border: none;
            }
        """)
        content_min_width = self.content.sizeHint().width() + 150
        self.setMinimumWidth(content_min_width)

        content_layout.addWidget(self.content, stretch=1)


        # -------------------------
        # Buttons
        # -------------------------
        self.btnDownload = QPushButton("Download")
        self.btnDelete = QPushButton("Delete")
        self.btnUpdate = QPushButton("Update")

        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        for btn in (
            self.btnDownload,
            self.btnDelete,
            self.btnUpdate
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

        content_layout.addLayout(btn_layout)

        layout.addWidget(content)

        # --- Button Callbacks ---
        self.btnDelete.clicked.connect(self._emit_delete)
        self.btnDownload.clicked.connect(self._emit_download)
        self.btnUpdate.clicked.connect(self._emit_update)


    def _emit_download(self):
        self.download.emit(self.plugin)

    def _emit_delete(self):
        self.delete.emit(self.plugin)

    def _emit_update(self):
        self.update_plugin.emit(self.plugin)

    def set_status(self, status=""):
        self.status_label.setText(f"({status})" if status else "")

    def set_state(self, state):
        """
        Set the complete visual state of the plugin widget.

        States:
            available
            downloading
            installed
            update_available
            updating
            deleting
            error
        """

        # First establish a clean baseline
        self.btnDownload.setVisible(False)
        self.btnUpdate.setVisible(False)
        self.btnDelete.setVisible(False)

        self.btnDownload.setEnabled(True)
        self.btnUpdate.setEnabled(True)
        self.btnDelete.setEnabled(True)

        if state == "available":
            self.set_status("")
            self.btnDownload.setVisible(True)

        elif state == "downloading":
            self.set_status("Downloading...")
            self.btnDownload.setVisible(True)
            self.btnDownload.setEnabled(False)

        elif state == "installed":
            self.set_status("Installed")
            self.btnDelete.setVisible(True)

        elif state == "update_available":
            self.set_status("Update available")
            self.btnUpdate.setVisible(True)
            self.btnDelete.setVisible(True)

        elif state == "updating":
            self.set_status("Updating...")
            self.btnUpdate.setVisible(True)
            self.btnUpdate.setEnabled(False)
            self.btnDelete.setVisible(False)

        elif state == "deleting":
            self.set_status("Deleting...")
            self.btnDelete.setVisible(True)
            self.btnDelete.setEnabled(False)

        elif state == "error":
            self.set_status("Operation failed")
            if self.btnDownload.isVisible():
                self.btnDownload.setEnabled(True)
            if self.btnUpdate.isVisible():
                self.btnUpdate.setEnabled(True)
            if self.btnDelete.isVisible():
                self.btnDelete.setEnabled(True)

class PluginStoreDialog(QDialog):
    task_finished = Signal(bool, object, object, object, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_manager = QApplication.instance().plugin_manager
        self.plugin_manager_dialog = QApplication.instance().plugin_manager_dialog
        self.state_manager = self.plugin_manager.state_manager
        self.channel = "osdag-plugins"
        self.plugins: list[PluginMetaData] = self.plugin_manager.discover_online_plugins(
            channel=self.channel)
        self.local_plugins: list[PluginMetaData] = self.plugin_manager.get_installed_plugins()
        self.updates_available = self._check_for_updates()
        
        self.plugin_store_threads = []
        self.plugin_store_workers = []

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("PluginStoreDialog")
        self.setWindowIcon(QIcon(":/images/osdag_logo.png"))

        # Size dialog relative to parent window
        if parent is not None:
            parent_size = parent.size()

            width = int(parent_size.width() * 0.80)
            height = int(parent_size.height() * 0.80)

            self.resize(width, height)

            # Keep the dialog usable on smaller parent windows
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
            # Sensible fallback when no parent is supplied
            self.resize(1000, 700)
            self.setMinimumSize(800, 600)

        # Layout and style
        self.setStyleSheet("""
            QDialog#PluginStoreDialog { background-color: #ffffff; border: 2px solid #90AF13; }
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
        self.titleBar.setTitle("Plugin Store")
        mainLayout.addWidget(self.titleBar)

        # Content
        contentWidget = QWidget(self)
        contentWidget.setObjectName("ContentWidget")
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(12, 10, 12, 10)
        contentLayout.setSpacing(10)

        # Logo
        self.logoLabel = QSvgWidget(
            ":/vectors/Osdag_light.svg",
            self
        )
        logo_height = max(55, min(85, int(self.height() * 0.10)))
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
                width: 10px;
                margin: 0px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #B8C58A;
                min-height: 35px;
                border-radius: 5px;
                margin: 1px;
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
                height: 10px;
                margin: 0px;
                border: none;
            }

            QScrollBar::handle:horizontal {
                background: #B8C58A;
                min-width: 35px;
                border-radius: 5px;
                margin: 1px;
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
                background: none;
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

        self.pluginContainer.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )
        scroll.setWidget(self.pluginContainer)

        # Populate plugins in the scroll area
        self._populate_plugins()

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
        self.okButton.clicked.connect(self.okClicked)
        buttonLayout.addWidget(self.okButton)

        contentLayout.addLayout(buttonLayout)
        mainLayout.addWidget(contentWidget)

        self.task_finished.connect(
            self._handle_task_finished,
            Qt.QueuedConnection
        )


    @Slot(bool, object, object, object, str)
    def _handle_task_finished(
        self, success, callback, widget, plugin, error
    ):
        callback(success, widget, plugin, error)

    def run_plugin_task(
        self,
        func: callable,
        state: str,
        plugin: PluginMetaData,
        widget: PluginWidget,
        callback
    ):
        widget.set_state(state)

        thread = QThread(self)
        worker = Worker(func, plugin)

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.finished.connect(
            lambda success, error: self.task_finished.emit(
                success, callback, widget, plugin, error
            )
        )

        worker.finished.connect(thread.quit)

        # Keep the worker alive until the thread finishes.
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Retain Python references.
        self.plugin_store_threads.append(thread)
        self.plugin_store_workers.append(worker)

        thread.finished.connect(
            lambda t=thread, w=worker: self._cleanup_plugin_task(t, w)
        )

        thread.start()

    def _cleanup_plugin_task(self, thread, worker):
        if thread in self.plugin_store_threads:
            self.plugin_store_threads.remove(thread)

        if worker in self.plugin_store_workers:
            self.plugin_store_workers.remove(worker)

    def delete_plugin(self, plugin: PluginMetaData, widget: PluginWidget):
        self.run_plugin_task(
            self.plugin_manager.delete_plugin,
            "deleting", plugin, widget,
            self._on_delete_finished
        )

    def download_plugin(self, plugin: PluginMetaData, widget: PluginWidget):
        self.run_plugin_task(
            self.plugin_manager.download_plugin,
            "downloading", plugin, widget,
            self._on_download_finished
        )

    def update_plugin(self, plugin: PluginMetaData, widget: PluginWidget):
        self.run_plugin_task(
            self.plugin_manager.update_plugin,
            "updating", plugin, widget,
            self._on_update_finished
        )

    def _on_delete_finished(self, success, widget, plugin, error=None):
        if success:
            print(f"[INFO] Successfully deleted plugin: {plugin.name}")
            self.plugin_manager_dialog.deactivate_plugin(plugin)
            self.plugin_manager.deactivate(plugin)
            self.plugin_manager.unregister_installed_plugin(plugin)
            self.plugin_manager_dialog.refresh_plugins()
            widget.set_state("available")
        else:
            print(f"[ERROR] Failed to delete plugin: {plugin.name}")
            print(f"{error}")
            widget.set_state("installed")

    def _on_download_finished(self, success, widget, plugin, error=""):
        if success:
            print(f"[INFO] Successfully downloaded plugin: {plugin.name}")
            self.plugin_manager._load_entry_point_plugins()
            widget.set_state("installed")

            # Activate by default
            self.plugin_manager.activate(plugin)
            self.plugin_manager_dialog.activate_plugin(plugin)
            self.plugin_manager_dialog.refresh_plugins()

        else:
            print(f"[INFO] Failed to download plugin: {plugin.name}")
            print(f"{error}")
            widget.set_state("available")

    def _on_update_finished(self, success, widget, plugin, error=None):
        if success:
            print(f"[INFO] Successfully updated plugin: {plugin.name}")
            installed_plugin = self.plugin_manager.get_plugin_by_name(plugin.name)
            self.plugin_manager.unregister_installed_plugin(installed_plugin)  # Remove old state
            
            self.plugin_manager._load_entry_point_plugins()  # Reload plugins to get the updated version

            self.plugin_manager_dialog.refresh_plugins()
            widget.set_state("installed")
        else:
            print(f"[INFO] Failed to update plugin: {plugin.name}")
            print(f"{error}")
            widget.set_state("installed")


    def refresh_plugins(self):
        # Re-discover both local and online plugins
        # self.plugins = self.plugin_manager.discover_online_plugins(channel="zehen-249")
        self.local_plugins = self.plugin_manager.state_manager.get_installed_plugins()
        self.updates_available = self._check_for_updates()

        # Clear all plugin widgets from the layout
        for i in reversed(range(self.pluginLayout.count())):
            widget = self.pluginLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Rebuild plugin list widgets
        self._populate_plugins()

    def _populate_plugins(self) -> None:

        def safe_parse_version(ver_string):
            """Safely parse version, returning 0.0.0 for invalid versions."""
            try:
                return version.parse(ver_string)
            except Exception:
                return version.parse("0.0.0")

        latest = {}
        for plugin in self.plugins:
            if plugin.name not in latest:
                latest[plugin.name] = plugin
            else:
                if safe_parse_version(plugin.version) > safe_parse_version(latest[plugin.name].version):
                    latest[plugin.name] = plugin

        self.plugins = list(latest.values())

        for plugin in self.plugins:
            pw = PluginWidget(plugin=plugin)

            pw.download.connect(
                lambda plugin, w=pw: self.download_plugin(plugin, w))
            pw.delete.connect(
                lambda plugin, w=pw: self.delete_plugin(plugin, w))
            pw.update_plugin.connect(
                lambda plugin, w=pw: self.update_plugin(plugin, w))

            pw.setMinimumHeight(90)
            pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            is_downloaded = any(
                lp.name == plugin.name for lp in self.local_plugins)

            if is_downloaded:
                is_update_available = any(
                    up.name == plugin.name
                    for up in self.updates_available
                )
                if self.plugin_manager.is_registered(plugin):
                    pw.set_state("installed")

                if is_update_available:
                    pw.set_state("update_available")
                else:
                    pw.set_state("installed")

            else:
                pw.set_state("available")

            self.pluginLayout.addWidget(pw)

    def _check_for_updates(self) -> list[PluginMetaData]:

        online_by_name = {p.name: p for p in self.plugins}

        updates_available = []
        for installed in self.local_plugins:
            online = online_by_name.get(installed.name)

            try:
                if online and version.parse(online.version) > version.parse(installed.version):
                    updates_available.append(online)
            except Exception as e:
                print(f"[WARN] Error checking update for {installed.name}: {e}")

        return updates_available

    def closeEvent(self, event):
        self.plugin_manager.state_manager.flush()
        self.plugin_manager_dialog.refresh_plugins()
        super().closeEvent(event)

    def okClicked(self):
        self.plugin_manager.state_manager.flush()
        self.plugin_manager_dialog.refresh_plugins()
        self.accept()


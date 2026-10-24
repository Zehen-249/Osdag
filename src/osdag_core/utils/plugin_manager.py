import json
import os
import subprocess
import sys
import requests
import platform
import tempfile
from dataclasses import dataclass, field
from threading import Lock, RLock
from importlib import metadata
from pathlib import Path
import pkgutil
import importlib
import uuid
from types import ModuleType
from collections import defaultdict
from typing import Type
from packaging.version import Version

from osdag_gui.plugin.plugin_base import PluginBase
from osdag_gui.plugin.window_plugin import WindowPlugin
from osdag_gui.plugin.widget_plugin import WidgetPlugin


@dataclass
class PluginMetaData:
    id: str = field(init=False)
    name: str
    plugin_type: Type[WindowPlugin] | Type[WidgetPlugin] = field(init=False)
    description: str = field(
        default_factory=lambda: "No description available.")
    authors: list[str] = field(default_factory=lambda: ["Unknown"])
    version: str = field(default_factory=lambda: "1.0.0")
    status: bool = field(default_factory=lambda: False)
    plugin_class: Type[WindowPlugin] | Type[WidgetPlugin] = field(default_factory=lambda: None)
    module_tree: list[tuple] | dict[str,list[tuple]] = field(default_factory=lambda: [("", "", None)])
    icons: list[str] = field(default_factory=lambda: [":/images/add_ons.png", ":/images/add_ons_clicked.png"])
    is_dev: bool = field(default_factory=lambda: False)
    online_avl: bool = field(init=False)
    download_size: int = field(init=False)
    online_ver: str = field(init=False)
    conda_channel: str = field(init=False)
    extra_channel_deps: list[str] = field(init=False)
    is_installed: bool = field(init=False)

    def __post_init__(self):
        self.id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{self.name}:{self.version}"
            )
        )
        if self.is_dev:
            self.is_installed = False
            
        if self.plugin_class is not None:
            plugin_package, class_name = self.plugin_class.split(":", 1)
            plugin_module = importlib.import_module(plugin_package)
            resolved_class = getattr(plugin_module, class_name)
            if resolved_class is None:
                raise AttributeError(
                    f"Plugin '{self.name}': class '{class_name}' "
                    f"was not found in module '{plugin_module}'."
                )
            if not issubclass(resolved_class, PluginBase):
                raise TypeError(
                    f"Plugin '{self.name}': '{plugin_module}:{class_name}' "
                    f"resolved to {resolved_class!r}, "
                    f"which is not a subclass of PluginBase."
                )
            self.plugin_class = resolved_class
            if issubclass(self.plugin_class, WindowPlugin):
                self.plugin_type = WindowPlugin
            elif issubclass(self.plugin_class, WidgetPlugin):
                self.plugin_type = WidgetPlugin
            else:
                raise TypeError(
                    f"Plugin '{self.name}': '{self.plugin_class}' "
                    f"is not a subclass of WindowPlugin or WidgetPlugin."
                )
        else:
            self.plugin_type = None
        
class PluginManager:
    def __init__(self):
        self.state_manager = StateManager()
        self.plugins: list[PluginMetaData] = []
        self.dev_plugins_paths: list[Path] = self.state_manager.get_plugin_paths()
        self.plugins_entry_point = metadata.entry_points().select(group="osdag.plugins")
        
    # ---------------------------
    # Plugin Discovery (Local Under Development & Installed Plugins)
    # ---------------------------
    def discover_local_plugins(self) -> list[PluginMetaData]:
        self.plugins.clear()

        self._load_entry_point_plugins()
        self._load_dev_plugins()

        # for plugin in self.plugins:
        #     plugin.status = self.state_manager.get_active_status(plugin.id)

        return self.plugins

    def _load_entry_point_plugins(self) -> None:
        try:
            for ep in self.plugins_entry_point:
                module = ep.load()
                if not getattr(module, "IS_OSDAG_PLUGIN", False):
                    print(
                        f"[WARN] Installed Osdag Plugin '{ep.name}' is not a valid plugin. IS_OSDAG_PLUGIN is not set to True.")
                    continue
                meta = getattr(module, "META", None)
                if not meta:
                    print(
                        f"[WARN] Installed plugin '{ep.name}' is missing META data."
                    )
                    continue
                if not isinstance(meta, dict):
                    print(
                        f"[WARN] Installed plugin '{ep.name}' has invalid META."
                    )
                    continue
                if not meta.get("name"):
                    print(f"[WARN] Installed plugin '{ep.name}' is missing 'name' in META.")
                    continue
                if not meta.get("plugin_class"):
                    print(
                        f"[WARN] Installed plugin '{ep.name}' is missing "
                        f"'plugin_class' in META."
                    )
                    continue

                if not meta.get("module_tree"):
                    print(
                        f"[WARN] Installed plugin '{ep.name}' is missing "
                        f"'module_tree' in META."
                    )
                    continue

                # Create metadata
                plugin = PluginMetaData(**meta)
                if not self.state_manager.is_registered(plugin.id):
                    plugin.status = True  # Mark as active if not registered
                    self.state_manager.update_state(plugin, plugin.status)
                    self.state_manager.add_installed_plugin(plugin) # Register the plugin as installed
                    # plugin.is_installed = True  # Mark as installed
                    # self.state_manager.register_plugin(plugin) # Register the plugin as installed
                else:
                    plugin.status = self.state_manager.get_status(plugin)
                    # plugin = PluginMetaData(**self.state_manager.get_state(plugin))  # Load the plugin state from the state manager
                    # plugin.status = self.state_manager.get_active_status(plugin.id)
                    # plugin.is_installed = self.state_manager.get_installed_status(plugin.id)

                self.plugins.append(plugin)

        except Exception as e:
            print(f"[WARN] Installed plugin loading failed: {e}")


    def _load_dev_plugins(self) -> None:
        for plugin_path in self.dev_plugins_paths:
            plugin_path = Path(plugin_path).resolve()
            print(f"[INFO] Loading development plugin from path: {plugin_path}")

            # Check folder
            if not plugin_path.exists():
                print(
                    f"[WARN] Development plugin path "
                    f"'{plugin_path}' does not exist."
                )
                continue

            if not plugin_path.is_dir():
                print(
                    f"[WARN] Development plugin path "
                    f"'{plugin_path}' is not a directory."
                )
                continue

            # Check package
            init_file = plugin_path / "__init__.py"

            if not init_file.exists():
                print(
                    f"[WARN] '{plugin_path}' does not contain "
                    f"__init__.py."
                )
                continue

            # Package name and import root
            package_name = plugin_path.name
            import_root = plugin_path.parent

            if str(import_root) not in sys.path:
                sys.path.insert(0, str(import_root))

            try:

                # Import package
                module = importlib.import_module(package_name)

                # Validate Osdag plugin
                if not getattr(module, "IS_OSDAG_PLUGIN", False):
                    print(
                        f"[WARN] '{package_name}' is not "
                        f"a valid Osdag plugin."
                    )
                    continue

                meta = getattr(module, "META", None)
                if not meta:
                    print(
                        f"[WARN] Installed plugin '{package_name}' is missing META data."
                    )
                    continue
                if not isinstance(meta, dict):
                    print(
                        f"[WARN] '{package_name}' has invalid META."
                    )
                    continue
                if not meta.get("name"):
                    print(
                        f"[WARN] '{package_name}' is missing "
                        f"'name' in META."
                    )
                    continue

                if not meta.get("plugin_class"):
                    print(
                        f"[WARN] '{package_name}' is missing "
                        f"'plugin_class' in META."
                    )
                    continue

                if not meta.get("module_tree"):
                    print(
                        f"[WARN] '{package_name}' is missing "
                        f"'module_tree' in META."
                    )
                    continue

                if not meta.get("is_dev"):
                    meta["is_dev"] = True  # Mark as development plugin
                    
                # Create metadata
                plugin = PluginMetaData(**meta)
                plugin.status = self.state_manager.get_status(plugin)
                self.state_manager.update_state(plugin, plugin.status)
                # if not self.state_manager.is_registered(plugin.id):
                #     plugin.status = True  # Mark as active if not registered
                #     plugin.is_installed = False  # Mark as not installed
                #     self.state_manager.register_plugin(plugin) # Register the plugin as installed
                # else:
                #     plugin = PluginMetaData(**self.state_manager.get_state(plugin))  # Load the plugin state from the state manager
                #     # plugin.status = self.state_manager.get_active_status(plugin.id)
                #     # plugin.is_installed = self.state_manager.get_installed_status(plugin.id)

                self.plugins.append(plugin)

            except Exception as e:
                print(
                    f"[WARN] Could not load development plugin "
                    f"'{package_name}': {e}"
                )

    def discover_online_plugins(
        self,
        channel: str
    ) -> list[PluginMetaData]:
        """
        Discover available plugins from a Conda channel.

        Selection rules:
            1. Always search noarch.
            2. Search the platform-specific subdir for the current system.
            3. For the same plugin name, select the latest version.
            4. If the same version exists in both noarch and the
            platform-specific repository, prefer the platform-specific
            package.
        """

        # ---------------------------------------------------------
        # Determine current Conda platform
        # ---------------------------------------------------------

        system = platform.system()
        machine = platform.machine().lower()
        _PLATFORM_SUBDIRS = {
            ("Windows", "amd64"): "win-64",
            ("Windows", "x86_64"): "win-64",
            ("Windows", "x64"): "win-64",
            ("Windows", "x86"): "win-32",
            ("Windows", "i386"): "win-32",
            ("Windows", "i686"): "win-32",
            ("Linux", "x86_64"): "linux-64",
            ("Linux", "amd64"): "linux-64",
            ("Linux", "aarch64"): "linux-aarch64",
            ("Linux", "arm64"): "linux-aarch64",
            ("Darwin", "arm64"): "osx-arm64",
            ("Darwin", "aarch64"): "osx-arm64",
            ("Darwin", "x86_64"): "osx-64",
            ("Darwin", "amd64"): "osx-64",
        }

        platform_subdir = _PLATFORM_SUBDIRS.get((system, machine))

        if platform_subdir is None:
            print(f"[WARN] Unsupported platform: {system} / {machine}")
            return []

        print(
            f"[INFO] Discovering online plugins for "
            f"{system} / {machine} ({platform_subdir})"
        )

        # ---------------------------------------------------------
        # Build repository URLs
        # ---------------------------------------------------------

        base_url = f"https://conda.anaconda.org/{channel}/label/main"

        urls = {
            "noarch": f"{base_url}/noarch/repodata.json",
            "platform": f"{base_url}/{platform_subdir}/repodata.json",
        }

        # ---------------------------------------------------------
        # Fetch package metadata separately
        # ---------------------------------------------------------

        packages_by_source = {}

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(self._fetch_url_pkgs, url): source
                for source, url in urls.items()
            }

            for future in as_completed(futures):
                source = futures[future]

                try:
                    packages_by_source[source] = future.result()
                except Exception as e:
                    print(
                        f"[WARN] Could not fetch {source} plugin metadata: {e}"
                    )
                    packages_by_source[source] = {}

        # ---------------------------------------------------------
        # Select the best package for each plugin
        # ---------------------------------------------------------

        selected_packages = {}

        # Platform-specific gets higher priority than noarch
        # when versions are equal.
        source_priority = {
            "noarch": 0,
            "platform": 1,
        }

        for source, packages in packages_by_source.items():

            for pkg_filename, info in packages.items():

                name = info.get("name", "")
                version = info.get("version", "1.0.0")

                if not name:
                    continue

                try:
                    parsed_version = Version(str(version))
                except Exception as e:
                    print(
                        f"[WARN] Invalid version '{version}' "
                        f"for package '{pkg_filename}': {e}"
                    )
                    continue

                candidate = {
                    "filename": pkg_filename,
                    "info": info,
                    "source": source,
                    "version": parsed_version,
                    "priority": source_priority[source],
                }

                current = selected_packages.get(name)

                if current is None:
                    selected_packages[name] = candidate
                    continue

                # -------------------------------------------------
                # Newer version wins
                # -------------------------------------------------

                if candidate["version"] > current["version"]:
                    selected_packages[name] = candidate

                # -------------------------------------------------
                # Same version:
                # platform-specific wins over noarch
                # -------------------------------------------------

                elif (
                    candidate["version"] == current["version"]
                    and candidate["priority"] > current["priority"]
                ):
                    selected_packages[name] = candidate

        # ---------------------------------------------------------
        # Create PluginMetaData
        # ---------------------------------------------------------

        online_plugins = []

        for name, selected in selected_packages.items():

            info = selected["info"]
            meta = {
                "name": info.get("name", ""),
                "description": info.get(
                    "summary",
                    "No description available."
                ),
                "authors": [
                    info.get(
                        "authors",
                        "Unknown"
                    )
                ],
                "version": info.get(
                    "version",
                    "1.0.0"
                ),
                "plugin_class": None,
                "module_tree": None,
            }
            plugin = PluginMetaData(**meta)
            plugin.online_avl = True
            plugin.download_size = round(
                info.get("size", 0) / (1024 * 1024),  # Convert bytes to MB
                2
            )
            plugin.online_ver = info.get(
                "version",
                "1.0.0"
            )
            plugin.conda_channel = channel
            online_plugins.append(plugin)

        return online_plugins

    def _fetch_url_pkgs(self, url: str):
        """Fetch and parse repodata.json from a conda channel and return packages."""
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        repo_data = resp.json()

        pkgs = {}
        pkgs.update(repo_data.get("packages", {}))
        pkgs.update(repo_data.get("packages.conda", {}))
        return pkgs

    # ---------------------------
    # State Management
    # ---------------------------
    def activate(self, plugin: PluginMetaData):
        print(f"[INFO] Activating plugin: {plugin.name}")
        if plugin:
            plugin.status = True
            self.state_manager.set_active_status(plugin.id, plugin.status)

    def deactivate(self, plugin: PluginMetaData):
        print(f"[INFO] Deactivating plugin: {plugin.name}")
        if plugin:
            plugin.status = False
            self.state_manager.set_active_status(plugin.id, plugin.status)

    def download_plugin(self, plugin: PluginMetaData) -> bool:
        print(f"[INFO] Downloading plugin: {plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "install",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{plugin.conda_channel}::{plugin.name}",
            "-y",
            "-c", "osdag",
            "-c", "zehen-249",
            "-c", "geompy",
            "-c", "conda-forge",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        # print(result.stdout)
        # print(result.stderr)
        if result.returncode == 0:
            if not self.state_manager.is_registered(plugin.id):
                plugin.status = True
                plugin.is_installed = True
                self.state_manager.register_plugin(plugin)

            # self.plugins.append(plugin)
            # After download, reload entry point plugins to load the newly installed plugin
            self._load_entry_point_plugins()
            return True
        return False

    def delete_plugin(self, plugin: PluginMetaData) -> bool:
        print(f"[INFO] Deleting plugin: {plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "remove",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{plugin.name}",
            "-y"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        # print(result.stdout)
        # print(result.stderr)
        if result.returncode == 0:
            self.plugins = [p for p in self.plugins if p.id != plugin.id]
            self.state_manager.delete_state(plugin)
            return True
        return False

    def update_plugin(self, plugin: PluginMetaData) -> bool:
        print(f"[INFO] Updating plugin: {plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "update",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{plugin.conda_channel}::{plugin.name}",
            "-y",
            "-c", "osdag",
            "-c", "zehen-249",
            "-c", "geompy",
            "-c", "conda-forge",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            self.state_manager.delete_state(plugin)  # Remove old state

            plugin.status = True
            plugin.is_installed = True
            plugin.version = plugin.online_ver  # Update to the new version
            plugin = PluginMetaData(**plugin.__dict__)  # Recreate the plugin metadata
            self.state_manager.register_installed_plugin(plugin) # Register the updated plugin
            return True
        else:
            print(f"[ERROR] Failed to update plugin '{plugin.name}'\n``: {result.stderr}")
        return False

    def get_plugin(self, plugin_id: str) -> PluginMetaData | None:
        for p in self.plugins:
            if p.id == plugin_id:
                return p
        return None

    def get_plugin_by_name(self, plugin_name: str) -> PluginMetaData | None:
        for p in self.plugins:
            if p.name.strip().lower() == plugin_name.strip().lower():
                return p
        return None

    # ---------------------------
    # Installed Plugin Registration
    # ---------------------------
    def register_installed_plugin(self, plugin: PluginMetaData) -> None:
        self.state_manager.register_plugin(plugin)

    def unregister_installed_plugin(self, plugin: PluginMetaData) -> None:
        self.state_manager.unregister_plugin(plugin.id)

    def is_registered(self, plugin: PluginMetaData) -> bool:
        return self.state_manager.is_registered(plugin.id)

    def get_installed_plugins(self) -> list[PluginMetaData]:
        return [
            self.get_plugin_by_name(x)
            for x in self.state_manager.get_installed_plugins()
        ]
    


class StateManager:
    def __init__(self):
        self.state_file = Path(__file__).resolve(
        ).parent.parent / "data" / "ResourceFiles" / "plugins" / "plugin_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        # Create the state file if it doesn't exist
        if not self.state_file.exists():
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4)
        self.plugins_paths_key = "__plugins_paths__"
        self._lock = RLock()
        self.states: dict = self._load_states()
        self._dirty = False

    def _load_states(self):
        if not os.path.exists(self.state_file):
            return {}
        with self._lock:
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(
                    f"[WARN] Could not load plugin state file {self.state_file}: {e}")
                return {}

    def register_plugin(self, plugin: PluginMetaData) -> None:
        with self._lock:
            if not self.is_registered(plugin.id):
                self.states[plugin.id] = plugin.__dict__
                self._dirty = True
                self.flush()

    def unregister_plugin(self, plugin_id: str) -> None:
        with self._lock:
            if self.is_registered(plugin_id):
                del self.states[plugin_id]
                self._dirty = True
                self.flush()

    def is_registered(self, plugin_id: str) -> bool:
        with self._lock:
            state = self.states.get(plugin_id, {})
            return state != {}
        
    def get_active_status(self, plugin_id: str) -> bool:
        with self._lock:
            if not self.is_registered(plugin_id):
                return False
            state = self.states.get(plugin_id, {})
            return state["status"]
            
    def set_active_status(self, plugin_id: str, status: bool) -> None:
        with self._lock:
            if self.is_registered(plugin_id):
                self.states[plugin_id]["status"] = status
                self._dirty = True
                self.flush()

    def get_installed_status(self, plugin_id: str) -> bool:
        with self._lock:
            if not self.is_registered(plugin_id):
                return False
            state = self.states.get(plugin_id, {})
            return state["is_installed"]
        
    def set_installed_status(self,  plugin_id: str, is_installed: bool) -> None:
        with self._lock:
            if self.is_registered(plugin_id):
                self.states[plugin_id]["is_installed"] = is_installed
                self._dirty = True
                self.flush()

    def get_state(self, plugin_id: str) -> dict:
        with self._lock:
            if not self.is_registered(plugin_id):
                return {}
            return self.states.get(plugin_id, {}).copy() if plugin_id in self.states else {}

    def set_state(self, plugin: PluginMetaData) -> None:
        with self._lock:
            if not self.is_registered(plugin.id):
                self.register_plugin(plugin)
            self.states[plugin.id] = plugin.__dict__
            self._dirty = True
            self.flush()

    def delete_state(self, plugin_id: str) -> None:
        with self._lock:
            if plugin_id in self.states:
                del self.states[plugin_id]
                self._dirty = True
                self.flush()

    def flush(self):
        with self._lock:
            if not self._dirty:
                return
            try:    
                self._atomic_save(self.states)
                self.states = self._load_states() # Reload states after saving to ensure consistency
                self._dirty = False
            except RuntimeError as e:
                print(
                    f"[ERROR] Failed to save plugin state file {self.state_file}: {e}")

    def _atomic_save(self, data: dict) -> None:
        temp_name = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.state_file.parent,
                prefix=f".{self.state_file.name}.",
                suffix=".tmp",
                delete=False,
                encoding="utf-8",
            ) as tmp:
                temp_name = tmp.name
                json.dump(data, tmp, indent=4)
                tmp.flush()
                os.fsync(tmp.fileno())

            # Atomic when source and destination are on the same filesystem.
            os.replace(temp_name, self.state_file)
            temp_name = None

        except (OSError, TypeError, ValueError) as e:
            raise RuntimeError(
                f"Failed to save plugin state file {self.state_file}"
            ) from e

        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass


    # Developement Plugins 
    def get_plugin_paths(self) -> list[Path]:
        with self._lock:
            paths = [Path(path) for path in self.states.get(self.plugins_paths_key, [])]
            return paths
        
    def add_plugin_path(self, path: str | Path) -> None:
        with self._lock:
            paths = self.states.get(self.plugins_paths_key, [])

            path = str(Path(path).resolve())

            if path not in paths:
                paths.append(path)
                self._dirty = True
                self.flush()
                
    def remove_plugin_path(self, path: str | Path) -> None:
        with self._lock:
            paths = self.states.get(
                self.plugins_paths_key,
                []
            )

            path = str(Path(path).resolve())

            if path in paths:
                paths.remove(path)
                self._dirty = True
                self.flush()
                
    # Installed Plugins        
    def get_installed_plugins(self) -> list[PluginMetaData]:
        temp_ls = []
        with self._lock:
            for plugin_id in list(self.states.keys()):
                state = self.states[plugin_id]
                if state["is_installed"] is True:
                    temp_ls.append(PluginMetaData(**self.states[plugin_id]))
        return temp_ls
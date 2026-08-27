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
    # module: object = field(default_factory=lambda: None)
    # entry_class: object = field(default_factory=lambda: None)
    module_tree: list[tuple] | dict[str,list[tuple]] = field(default_factory=lambda: [("", "", None)])
    icons: list[str] = field(default_factory=lambda: [":/images/add_ons.png", ":/images/add_ons_clicked.png"])
    is_dev: bool = field(default_factory=lambda: False)
    online_avl: bool = field(init=False)
    download_size: int = field(init=False)
    online_ver: str = field(init=False)
    conda_channel: str = field(init=False)

    def __post_init__(self):
        self.id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{self.name}:{self.version}"
            )
        )
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
        self.window_plugins = defaultdict()
        print(f"[INFO] PluginManager initialized.")
        
    # ---------------------------
    # Plugin Discovery (Local Under Development & Installed Plugins)
    # ---------------------------
    def discover_local_plugins(self) -> list[PluginMetaData]:
        self.plugins.clear()

        self._load_entry_point_plugins()
        self._load_dev_plugins()

        for plugin in self.plugins:
            plugin.status = self.state_manager.get_status(plugin)

        return self.plugins

    def _load_entry_point_plugins(self) -> None:
        try:
            for ep in self.plugins_entry_point:
                module = ep.load()
                if not getattr(module, "IS_OSDAG_PLUGIN", False):
                    print(
                        f"[WARN] Installed Plugin '{ep.name}' is not a valid OSDAG plugin.")
                    continue
                meta = getattr(module, "META", {})
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
                if not self.state_manager.is_registered(plugin):
                    self.activate(plugin)
                    self.state_manager.add_installed_plugin(plugin)

                self.plugins.append(plugin)

                # if "osdag_plugin_" in name:
                #     name = name[len("osdag_plugin_"):]
                #     meta["name"] = name
                # entry_point = getattr(module, "ENTRY_POINT", None)
                # entry_class = self._resolve_entry_class(
                #     module, name, entry_point)
                # if entry_class:
                #     self.plugins.append(PluginMetaData(
                #         **meta, status=False, module=module, entry_class=entry_class))
                # else:
                #     print(
                #         f"[WARN] Entry point '{ep.name}' could not resolve entry class.")
                #     continue
        except Exception as e:
            print(f"[WARN] Installed plugin loading failed: {e}")

    # def _load_dev_plugins(self) -> None:
    #     if not self.dev_plugins_paths:
    #         print("[INFO] No development plugins paths configured.")
    #         return
    #     for plugin_root in self.dev_plugins_paths:
    #         if not plugin_root.exists():
    #             print(
    #                 f"[WARN] Development plugins path '{plugin_root}' does not exist.")
    #             continue
    #         if not plugin_root.is_dir():
    #             print(
    #                 f"[WARN] Development plugins path '{plugin_root}' is not a directory.")
    #             continue

    #         # Add workspace root to sys.path so plugins can be imported
    #         workspace_root = plugin_root.parent
    #         if str(workspace_root) not in sys.path:
    #             sys.path.insert(0, str(workspace_root))

    #         for pkg_dir in plugin_root.iterdir():
    #             if not pkg_dir.is_dir():
    #                 continue
    #             for _, name, ispkg in pkgutil.iter_modules([str(pkg_dir)]):
    #                 if not ispkg:
    #                     continue
    #                 if name in [p.name for p in self.plugins]:
    #                     print(
    #                         f"[INFO] Development plugin '{name}' is already loaded from osdag.plugins entry point.")
    #                     continue
    #                 try:
    #                     module = importlib.import_module(
    #                         f"{pkg_dir.name}.{name}")
    #                     if not getattr(module, "IS_OSDAG_PLUGIN", False):
    #                         print(
    #                             f"[WARN] Development plugin '{name}' is not a valid OSDAG plugin.")
    #                         continue
    #                     meta = getattr(module, "META", {})
    #                     plugin_name = meta.get("name")
    #                     if plugin_name is None:
    #                         print(f"[WARN] Development plugin '{name}' is missing 'name'.")
    #                         continue
    #                     self.plugins.append(PluginMetaData(
    #                         **meta, status=False, plugin_class=entry_class))
    #                     # entry_class = self._resolve_entry_class(
    #                     #     module, plugin_name, getattr(module, "ENTRY_POINT", None))
    #                     # if entry_class:
    #                     #     self.plugins.append(PluginMetaData(
    #                     #         **meta, status=False, plugin_class=entry_class))
    #                     # else:
    #                     #     print(
    #                     #         f"[WARN] Development plugin '{name}' could not resolve entry class.")
    #                 except Exception as e:
    #                     print(f"[WARN] Could not load Development plugin '{name}': {e}")

    # # def _resolve_entry_class(self, module: ModuleType, name: str, entry_path: str) -> object | None:
    #     if not entry_path:
    #         print(f"[WARN] Plugin '{name}' missing 'ENTRY_POINT'.")
    #         return None
    #     try:
    #         parts = entry_path.split(".")
    #         submodule_name = ".".join(parts[:-1])
    #         class_name = parts[-1]
    #         entry_module = importlib.import_module(
    #             f"{module.__name__}" + (f".{submodule_name}" if submodule_name else ""))
    #         return getattr(entry_module, class_name)
    #     except Exception as e:
    #         print(
    #             f"[WARN] Could not resolve entry class '{entry_path}' for plugin '{name}': {e}")
    #         return None

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
                self.plugins.append(PluginMetaData(**meta))

            except Exception as e:
                print(
                    f"[WARN] Could not load development plugin "
                    f"'{package_name}': {e}"
                )
        
    # def discover_online_plugins(self, channel: str) -> list[PluginMetaData]:
    #     """Discover available plugins from conda channel (metadata only).
    #     After downloading, plugins will be loaded via entry points."""
    #     urls = [f"https://conda.anaconda.org/{channel}/label/main/noarch/repodata.json",f"https://conda.anaconda.org/{channel}/label/main/win-64/repodata.json",f"https://conda.anaconda.org/{channel}/label/main/linux-64/repodata.json"]
    #     pkgs = self._fetch_channel_pkgs(urls=urls)
    #     online_plugins = []
    #     for pkg_filename, info in pkgs.items():
    #         meta = {
    #             "name": info.get("name", ""),
    #             "description": info.get("summary", "No description available."),
    #             "authors": [info.get("author", "Unknown")],
    #             "version": info.get("version", "1.0.0"),
    #             "plugin_class": None,  # Will be loaded after download
    #             "module_tree": None,  # Will be loaded after download
    #         }
    #         # Online plugins are returned as available for download only
    #         # After download, they will be loaded via _load_entry_point_plugins()
    #         online_plugins.append(PluginMetaData(**meta))
    #     return online_plugins

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

        if system == "Windows":
            if machine in ("amd64", "x86_64", "x64"):
                platform_subdir = "win-64"
            elif machine in ("x86", "i386", "i686"):
                platform_subdir = "win-32"
            else:
                print(
                    f"[WARN] Unsupported Windows architecture: {machine}"
                )
                return []

        elif system == "Linux":
            if machine in ("x86_64", "amd64"):
                platform_subdir = "linux-64"
            elif machine in ("aarch64", "arm64"):
                platform_subdir = "linux-aarch64"
            else:
                print(
                    f"[WARN] Unsupported Linux architecture: {machine}"
                )
                return []

        elif system == "Darwin":
            if machine in ("arm64", "aarch64"):
                platform_subdir = "osx-arm64"
            elif machine in ("x86_64", "amd64"):
                platform_subdir = "osx-64"
            else:
                print(
                    f"[WARN] Unsupported macOS architecture: {machine}"
                )
                return []

        else:
            print(
                f"[WARN] Unsupported operating system: {system}"
            )
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

        for source, url in urls.items():
            try:
                packages_by_source[source] = self._fetch_url_pkgs(url=url)
            except Exception as e:
                print(
                    f"[WARN] Could not fetch {source} plugin metadata "
                    f"from {url}: {e}"
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
            self.state_manager.update_state(plugin, plugin.status)

    def deactivate(self, plugin: PluginMetaData):
        print(f"[INFO] Deactivating plugin: {plugin.name}")
        if plugin:
            plugin.status = False
            self.state_manager.update_state(plugin, plugin.status)

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
        # print(result.stdout)
        # print(result.stderr)
        if result.returncode == 0:
            return True
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
        self.state_manager.add_installed_plugin(plugin)

    def unregister_installed_plugin(self, plugin: PluginMetaData) -> None:
        self.state_manager.remove_installed_plugin(plugin)

    def is_registered(self, plugin: PluginMetaData) -> bool:
        return self.state_manager.is_registered(plugin)

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
        self.installed_plugins_key = "__installed_plugins__"
        self._lock = RLock()
        self.states: dict = self._load_states()
        self._dirty = False
        print(f"[INFO] StateManager initialized")

    def _load_states(self):
        if not os.path.exists(self.state_file):
            return {}
        with self._lock:
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(
                    f"[WARN] Could not load state file {self.state_file}: {e}")
                return {}

    def get_status(self, plugin: PluginMetaData) -> bool:
        with self._lock:
            return self.states.get(plugin.id, False)

    def update_state(self, plugin: PluginMetaData, status: bool) -> None:
        with self._lock:
            prev = self.states.get(plugin.id)
            if prev is None:
                plugin.status = True
                self.states[plugin.id] = plugin.status
                return
            if prev != status:
                self.states[plugin.id] = status
                self._dirty = True

    def delete_state(self, plugin: PluginMetaData) -> None:
        with self._lock:
            if plugin.id in self.states:
                del self.states[plugin.id]
                self._dirty = True

    def flush(self):
        with self._lock:
            if not self._dirty:
                return
            self._atomic_save(self.states)
            self._dirty = False

    def _atomic_save(self, data: dict):
        dir_name = os.path.dirname(self.state_file)
        if not dir_name:
            dir_name = "."
        try:
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp:
                json.dump(data, tmp, indent=4)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self.state_file)
        except Exception as e:
            print(
                f"[ERROR] Failed to save state file {self.state_file}: {e}")


    # Developement Plugins 
    def get_plugin_paths(self) -> list[Path]:
        with self._lock:
            paths = [Path(path) for path in self.states.get(self.plugins_paths_key, [])]
            return paths
        
    def add_plugin_path(self, path: str | Path) -> None:
        with self._lock:
            paths = self.states.setdefault(
                self.plugins_paths_key,
                []
            )

            path = str(Path(path).resolve())

            if path not in paths:
                paths.append(path)
                self._dirty = True
                
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

    # Installed Plugins
    def add_installed_plugin(self, plugin: PluginMetaData) -> None:
        with self._lock:
            installed_plugins = self.states.setdefault(
                self.installed_plugins_key,
                []
            )
            if plugin.name not in installed_plugins:
                installed_plugins.append(plugin.name)
            self._dirty = True
            self.flush()

    def remove_installed_plugin(self, plugin: PluginMetaData) -> None:
        with self._lock:
            installed_plugins = self.states.get(
                self.installed_plugins_key,
                []
            )
            if plugin.name in installed_plugins:
                installed_plugins.remove(plugin.name)
            self.states.remove(plugin.id)  # Remove the plugin's status as well
            self._dirty = True
            self.flush()


    def is_registered(self, plugin: PluginMetaData) -> bool:
        with self._lock:
            installed_plugins = self.states.get(
                self.installed_plugins_key,
                []
            )
            return plugin.name in installed_plugins

    def get_installed_plugins(self) -> list[str]:
        with self._lock:
            return self.states.get(
                self.installed_plugins_key,
                []
            )
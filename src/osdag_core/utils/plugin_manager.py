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
    id: str = field(default_factory=lambda: "")
    name: str = field(default_factory=lambda: "Unnamed Plugin")
    description: str = field(
        default_factory=lambda: "No description available.")
    authors: list[str] = field(default_factory=lambda: ["Unknown"])
    version: str = field(default_factory=lambda: "1.0.0")
    status: bool = field(default_factory=lambda: False)
    plugin_class: str | Type[WindowPlugin] | Type[WidgetPlugin] | None = field(default_factory=lambda: None)
    module_tree: list[tuple] | dict[str,list[tuple]] = field(default_factory=lambda: [("", "", None)])
    icons: list[str] = field(default_factory=lambda: [":/images/add_ons.png", ":/images/add_ons_clicked.png"])
    conda_channel: str = field(default_factory=lambda: "")
    extra_channel_deps: list[str] = field(default_factory=list)
    is_dev: bool = field(default_factory=lambda: False)

    plugin_type: Type[WindowPlugin] | Type[WidgetPlugin] = field(default_factory=lambda: None)
    dev_path: str | None = field(default_factory=lambda: None)
    online_avl: bool = field(default_factory=lambda: False)
    download_size: int = field(default_factory=lambda: 0)
    online_ver: str = field(default_factory=lambda: "")
    update_avl: bool = field(default_factory=lambda: False)
    is_installed: bool = field(default_factory=lambda: False)


    def __post_init__(self):
        if self.is_dev:
            self.is_installed = False
            self.name = f"{self.name} (dev)" if not self.name.endswith("(dev)") else self.name

        if self.is_installed:
            self.is_dev = False

        self.id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{self.name}:{self.version}"
            )
        )
            
        if self.plugin_class is not None:
            # Resolve plugin class if provided as an import string
            if isinstance(self.plugin_class, str):
                plugin_package, class_name = self.plugin_class.split(":", 1)
                plugin_module = importlib.import_module(plugin_package)
                resolved_class = getattr(plugin_module, class_name, None)

                if resolved_class is None:
                    raise AttributeError(
                        f"Plugin '{self.name}': class '{class_name}' "
                        f"was not found in module '{plugin_package}'."
                    )

                self.plugin_class = resolved_class

            # Validate resolved plugin class
            if not isinstance(self.plugin_class, type):
                raise TypeError(
                    f"Plugin '{self.name}': plugin_class must be a "
                    f"class or import-path string, got {type(self.plugin_class).__name__}."
                )

            if not issubclass(self.plugin_class, PluginBase):
                raise TypeError(
                    f"Plugin '{self.name}': '{self.plugin_class}' "
                    f"is not a subclass of PluginBase."
                )

            # Determine plugin type
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "plugin_type": (
                f"{self.plugin_type.__module__}:{self.plugin_type.__qualname__}"
                if self.plugin_type else None
            ),
            "description": self.description,
            "authors": self.authors,
            "version": self.version,
            "status": self.status,
            "plugin_class": (
                f"{self.plugin_class.__module__}:{self.plugin_class.__qualname__}"
                if isinstance(self.plugin_class, type)
                else self.plugin_class
            ),
            "module_tree": self.module_tree,
            "icons": self.icons,
            "is_dev": self.is_dev,
            "dev_path": self.dev_path,
            "online_avl": self.online_avl,
            "download_size": self.download_size,
            "online_ver": self.online_ver,
            "conda_channel": self.conda_channel,
            "extra_channel_deps": self.extra_channel_deps,
            "is_installed": self.is_installed,
        }

    @classmethod
    def from_dict(cls, data: dict):
        data = data.copy()
        for key in ("plugin_class", "plugin_type"):
            value = data.get(key)

            if isinstance(value, str) and ":" in value:
                module_path, class_name = value.split(":", 1)
                module = importlib.import_module(module_path)
                data[key] = getattr(module, class_name)

        # Restore tuples in module_tree
        if isinstance(data.get("module_tree"), list):
            data["module_tree"] = [
                tuple(item) if isinstance(item, list) else item
                for item in data["module_tree"]
            ]
        return cls(**data)

class PluginManager:
    def __init__(self):
        self.state_manager = StateManager()
        self.local_plugins: list[PluginMetaData] = []
        self.online_plugins: list[PluginMetaData] = []
        self.dev_plugins_paths: list[Path] = self.get_dev_plugin_paths()
        self.plugins_entry_point = metadata.entry_points().select(group="osdag.plugins")
        
    # ---------------------------
    # Plugin Discovery (Local Under Development & Installed Plugins)
    # ---------------------------
    def discover_local_plugins(self) -> list[PluginMetaData]:
        self.local_plugins.clear()

        # self._load_entry_point_plugins()
        # self._load_dev_plugins()
        self.local_plugins = self.get_installed_plugins() + self.get_dev_plugins()
        # for plugin in self.local_plugins:
        #     plugin.status = self.state_manager.get_active_status(plugin.id)

        return self.local_plugins

    def _load_entry_point_plugins(self) -> PluginMetaData | None:
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
                plugin.is_installed = True  # Mark as installed plugin
                if not self.is_registered(plugin):
                    self.register_installed_plugin(plugin)  # Register the plugin as installed
                else:
                    plugin = self.get_plugin_state(plugin)  # Load the plugin state from the state manager

                self.local_plugins.append(plugin)

        except Exception as e:
            print(f"[WARN] Installed plugin loading failed: {e}")


    def _load_dev_plugins(self) -> None:

        for plugin_path in self.dev_plugins_paths:
            plugin_path = Path(plugin_path).resolve()

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
                    
                meta["dev_path"] = str(plugin_path)  # Store the development path
                    
                # Create metadata
                plugin = PluginMetaData(**meta)
                if not self.is_registered(plugin):
                    self.register_dev_plugin(plugin)  # Register development plugin

                else:
                    plugin = self.get_plugin_state(plugin)  # Load the plugin state from the state manager

                self.local_plugins.append(plugin)

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
            plugin.extra_channel_deps = info.get("extra_channel_deps", [])
            online_plugins.append(plugin)

        self.online_plugins = online_plugins

        # for inst, online in zip(self.local_plugins, self.online_plugins):
        #     if inst.name == online.name and (Version(inst.version) < Version(online.online_ver) and inst.online_avl == False):
        #         inst.online_avl = True
        #         inst.download_size = online.download_size
        #         inst.online_ver = online.online_ver
        #         inst.conda_channel = online.conda_channel
        #         inst.extra_channel_deps = online.extra_channel_deps
        #         if Version(inst.version) < Version(online.online_ver):
        #             inst.update_avl = True
    
        return self.online_plugins

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
        if plugin:
            plugin.status = True
            self.set_active_status(plugin)

    def deactivate(self, plugin: PluginMetaData):
        if plugin:
            plugin.status = False
            self.set_active_status(plugin)

    def download_plugin(self, store_plugin: PluginMetaData) -> bool:
        print(f"[INFO] Downloading plugin: {store_plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "install",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{store_plugin.conda_channel}::{store_plugin.name}",
            "-y",
            "-c", store_plugin.conda_channel,
            "-c", "osdag",
            "-c", "osdag-plugins",
            "-c", "geompy",
            "-c", "conda-forge",
        ]
        # Add extra channels, if available
        for dep in getattr(store_plugin, "extra_channel_deps", []):
            cmd.extend(["-c", dep])

        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True)
        
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            print(f"[ERROR] Download failed:\n{error}")
            return False, error
        
        print(f"[INFO] Successfully downloaded: {store_plugin.name}")
        return True, ""

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
            self.local_plugins = [p for p in self.local_plugins if p.id != plugin.id]
            self.unregister_installed_plugin(plugin.id)
            return True , ""
        return False, result.stderr.strip() or result.stdout.strip()

    def update_plugin(self, store_plugin: PluginMetaData) -> bool:
        print(f"[INFO] Updating plugin: {store_plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "update",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{store_plugin.name}",
            "-y",
            "-c", store_plugin.conda_channel,
            "-c", "osdag",
            "-c", "osdag-plugins",
            "-c", "geompy",
            "-c", "conda-forge",
        ] 
        # Add extra channels, if available
        for dep in getattr(store_plugin, "extra_channel_deps", []):
            cmd.extend(["-c", dep])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        else:
            print(f"[ERROR] Failed to update plugin '{store_plugin.name}'\n``: {result.stderr}")
        return False, result.stderr.strip() or result.stdout.strip()

    def set_active_status(self, plugin: PluginMetaData) -> None:
        self.state_manager.set_active_status(plugin.id, plugin.status)

    def get_plugin(self, plugin_id: str) -> PluginMetaData | None:
        for p in self.local_plugins:
            if p.id == plugin_id:
                return p
        return None

    def get_plugin_by_name(self, plugin_name: str) -> PluginMetaData | None:
        for p in self.local_plugins:
            if p.name.strip().lower() == plugin_name.strip().lower():
                return p
        return None

    def get_plugin_state(self, plugin_id: str) -> PluginMetaData | None:
        return self.state_manager.get_state(plugin_id)

    # ---------------------------
    # Installed Plugin Registration
    # ---------------------------
    def register_installed_plugin(self, plugin: PluginMetaData) -> None:
        plugin.status = True
        plugin.is_installed = True
        self.state_manager.register_plugin(plugin)

    def unregister_installed_plugin(self, plugin: PluginMetaData) -> None:
        self.state_manager.unregister_plugin(plugin.id)

    def is_registered(self, plugin: PluginMetaData) -> bool:
        return self.state_manager.is_registered(plugin.id)

    def update_installed_plugin_state(self, plugin: PluginMetaData) -> None:
        plugin = PluginMetaData(**plugin.to_dict())  # Recreate the plugin metadata
        self.state_manager.set_state(plugin)

    def get_installed_plugins(self) -> list[PluginMetaData]:
        return self.state_manager.get_installed_plugins()
    
    # ---------------------------
    # Development Plugin Registration
    # ---------------------------
    def get_dev_plugin_paths(self) -> list[Path]:
        return self.state_manager.get_plugin_paths()

    def get_dev_plugin_by_path(self, path: str | Path) -> PluginMetaData | None:
        return self.state_manager.get_plugin_by_dev_path(path)
    
    def register_dev_plugin_path(self, path: str | Path) -> None:
        self.state_manager.add_plugin_path(path)
        self.dev_plugins_paths = self.get_dev_plugin_paths()  # Update the local list

    def register_dev_plugin(self, plugin: PluginMetaData) -> None:
        plugin.status = True
        plugin.is_dev = True
        plugin = PluginMetaData(**plugin.to_dict())  # Recreate the plugin metadata
        self.state_manager.register_plugin(plugin)

    def unregister_dev_plugin_path(self, path: str | Path) -> None:
        self.state_manager.remove_plugin_path(path)
        self.dev_plugins_paths = self.get_dev_plugin_paths()  # Update the local list

    def is_dev_plugin_path_registered(self, path: str | Path) -> bool:
        return Path(path).resolve() in self.dev_plugins_paths

    def clear_dev_plugin_paths(self) -> None:
        for path in self.dev_plugins_paths:
            self.state_manager.remove_plugin_path(path)
        self.dev_plugins_paths = self.get_dev_plugin_paths()  # Update the local list

    def get_dev_plugins(self) -> list[PluginMetaData]:
        return self.state_manager.get_dev_plugins()


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
        self.states: dict[str:PluginMetaData] = self._load_states()
        self._dirty = False

    def _load_states(self):
        if not os.path.exists(self.state_file):
            return {}

        with self._lock:
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Load development plugin paths before importing plugin classes
                dev_plugins_paths = data.get("__plugins_paths__", [])

                for plugin_path in dev_plugins_paths:
                    plugin_path = Path(plugin_path).resolve()

                    if not plugin_path.is_dir():
                        print(
                            f"[WARN] Development plugin path does not exist: "
                            f"{plugin_path}"
                        )
                        continue

                    import_root = str(plugin_path.parent)

                    if import_root not in sys.path:
                        sys.path.insert(0, import_root)

                # Deserialize plugin metadata
                states = {
                    "__plugins_paths__": dev_plugins_paths
                }

                for plugin_id, plugin_data in data.items():
                    if plugin_id == "__plugins_paths__":
                        continue

                    if isinstance(plugin_data, dict):
                        states[plugin_id] = PluginMetaData.from_dict(plugin_data)

                return states

            except (json.JSONDecodeError, OSError) as e:
                print(
                    f"[WARN] Could not load plugin state file "
                    f"{self.state_file}: {e}"
                )
                return {}

    def register_plugin(self, plugin: PluginMetaData) -> None:
        with self._lock:
            if not self.is_registered(plugin.id):
                self.states[plugin.id] = plugin
                self._dirty = True
                self.flush()  # Save the state immediately after registration

    def unregister_plugin(self, plugin_id: str) -> None:
        with self._lock:
            if self.is_registered(plugin_id):
                del self.states[plugin_id]
                self._dirty = True
                self.flush()  # Save the state immediately after registration

    def is_registered(self, plugin_id: str) -> bool:
        with self._lock:
            state = self.states.get(plugin_id, None)
            return state is not None and isinstance(state, PluginMetaData)
        
    def get_active_status(self, plugin_id: str) -> bool:
        with self._lock:    
            if not self.is_registered(plugin_id):
                return False
            state = self.states.get(plugin_id, {})
            return state.status if isinstance(state, PluginMetaData) else False
            
    def set_active_status(self, plugin_id: str, status: bool) -> None:
        with self._lock:
            if self.is_registered(plugin_id):
                self.states[plugin_id].status = status
                self._dirty = True
                self.flush()  # Save the state immediately after registration

    def get_installed_status(self, plugin_id: str) -> bool:
        with self._lock:
            if not self.is_registered(plugin_id):
                return False
            state = self.states.get(plugin_id, {})
            return state.is_installed if isinstance(state, PluginMetaData) else False
        
    def set_installed_status(self,  plugin_id: str, is_installed: bool) -> None:
        with self._lock:
            if self.is_registered(plugin_id):
                self.states[plugin_id].is_installed = is_installed
                self._dirty = True
                self.flush()  # Save the state immediately after registration

    def get_state(self, plugin_id: str) -> PluginMetaData | None:
        with self._lock:
            if not self.is_registered(plugin_id):
                return None
            return self.states.get(plugin_id, None)

    def set_state(self, plugin: PluginMetaData) -> None:
        with self._lock:
            if not self.is_registered(plugin.id):
                self.register_plugin(plugin)
            self.states[plugin.id] = plugin
            self._dirty = True
            self.flush()  # Save the state immediately after registration

    def flush(self):
        with self._lock:
            if not self._dirty:
                return
            try:    
                serializable_states = {}
                for key, plugin in self.states.items():
                    if key == "__plugins_paths__":
                        serializable_states[key] = plugin
                    else:
                        serializable_states[key] = plugin.to_dict()

                self._atomic_save(serializable_states)
                self.states = self._load_states() # Reload states after saving to ensure consistency
                self._dirty = False
            except Exception as e:
                raise RuntimeError(
                    f"Failed to save plugin state file {self.state_file}: "
                    f"{type(e).__name__}: {e}"
                ) from e

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
            paths = self.states.get(self.plugins_paths_key)
            if paths is None:
                paths = []
                self.states[self.plugins_paths_key] = paths

            path = str(Path(path).resolve())
            if path not in paths:
                self.states[self.plugins_paths_key].append(path)
                self._dirty = True

    def remove_plugin_path(self, path: str | Path) -> None:
        with self._lock:
            paths = self.states.get(
                self.plugins_paths_key,
                []
            )

            path = str(Path(path).resolve())

            if path in paths:
                self.states[self.plugins_paths_key].remove(path)
                plugin = self.get_plugin_by_dev_path(path)
                if plugin:
                    self.unregister_plugin(plugin.id)
                self._dirty = True

    def get_plugin_by_dev_path(self, path: str | Path) -> PluginMetaData | None:
        with self._lock:
            for plugin_id, state in self.states.items():
                if plugin_id == self.plugins_paths_key:
                    continue
                if isinstance(state, PluginMetaData) and state.is_dev and state.dev_path == str(Path(path).resolve()):
                    return state
        return None
    
    def get_dev_plugins(self) -> list[PluginMetaData]:
        dev_plugins = []
        with self._lock:
            for plugin_id in list(self.states.keys()):
                if plugin_id == self.plugins_paths_key:
                    continue
                state = self.states[plugin_id]
                if state.is_dev if hasattr(state, 'is_dev') else False:
                    dev_plugins.append(state)
        return dev_plugins

                
    # Installed Plugins        
    def get_installed_plugins(self) -> list[PluginMetaData]:
        temp_ls = []
        with self._lock:
            for plugin_id in list(self.states.keys()):
                if plugin_id == self.plugins_paths_key:
                    continue
                state = self.states[plugin_id]
                if state.is_installed if hasattr(state, 'is_installed') else False:
                    temp_ls.append(state)
        return temp_ls
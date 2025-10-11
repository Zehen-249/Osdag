import json
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
import pkgutil
import importlib

@dataclass
class PluginState:
    name: str
    status: str = field(default_factory=lambda: "Inactive")

@dataclass
class PluginMetaData:      
    name: str
    description: str = field(default_factory=lambda: "No description available.")
    authors: list = field(default_factory=lambda: [{"name": "Unknown"}])
    version: str = field(default_factory=lambda: "1.0.0")
    status: str = field(default_factory=lambda: "Inactive")
    module: object = field(default=None)
    entry_class: object = field(default=None)

class PluginManager:
    def __init__(self):
        self.file_path = Path.home() / ".osdag" / "plugins_state.json"
        self.file_path.parent.mkdir(exist_ok=True)
        self._states: dict[str, PluginState] = self._load()

    def _load(self) -> dict[str, PluginState]:
        if self.file_path.exists():
            try:
                data = json.loads(self.file_path.read_text())
                return {k: PluginState(name=k, status=v) for k, v in data.items()}
            except json.JSONDecodeError:
                pass
        return {}

    def save(self):
        data = {name: s.status for name, s in self._states.items()}
        self.file_path.write_text(json.dumps(data, indent=4))

    def get(self, name: str) -> str:
        return self._states.get(name, PluginState(name)).status

    def set(self, name: str, status: str):
        self._states[name] = PluginState(name, status)
        self.save()

    def remove(self, name: str):
        self._states.pop(name, None)
        self.save()

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


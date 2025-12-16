from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable[..., str]
    description: str
    signature: str


_TOOLS: dict[str, ToolSpec] = {}
_DISCOVERED: bool = False


def tool(func: Callable[..., str]) -> Callable[..., str]:
    name = func.__name__
    doc = inspect.getdoc(func) or ""
    sig = str(inspect.signature(func))
    _TOOLS[name] = ToolSpec(name=name, func=func, description=doc, signature=sig)
    return func


def _discover_package(pkg_name: str) -> None:
    pkg = importlib.import_module(pkg_name)
    pkg_path = getattr(pkg, "__path__", None)
    if not pkg_path:
        return

    prefix = pkg.__name__ + "."
    for mod in pkgutil.iter_modules(pkg_path, prefix):
        full_name = mod.name
        short = full_name.rsplit(".", 1)[-1]
        if short.startswith("_") or short in {"registry"}:
            continue
        try:
            importlib.import_module(full_name)
        except Exception:
            # best-effort discovery: ignore modules that fail to import
            continue
        if mod.ispkg:
            _discover_package(full_name)


def discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    _discover_package("tools")


def get_tools_map() -> dict[str, Callable[..., str]]:
    discover()
    return {name: spec.func for name, spec in _TOOLS.items()}


def get_tool_specs() -> dict[str, ToolSpec]:
    discover()
    return dict(_TOOLS)


def build_tools_section() -> str:
    specs = list(get_tool_specs().values())
    specs.sort(key=lambda s: s.name)

    lines: list[str] = ["Tools:"]
    for i, spec in enumerate(specs, start=1):
        lines.append(f"\n{i}) {spec.name}{spec.signature}")
        if spec.description:
            for line in spec.description.splitlines():
                lines.append(f"    {line}")
    return "\n".join(lines).rstrip() + "\n"


def build_system_tools_description(extra_rules: Optional[str] = None) -> str:
    base = (
        "You have access to the following tools. When you want to call a tool, you MUST respond\n"
        "ONLY with valid JSON:\n"
        "- Either a single object: {\"tool\": \"...\", \"args\": {...}}\n"
        "- Or an array of such objects, if the user asked for multiple actions (keep the order of execution).\n\n"
    )
    txt = base + build_tools_section()
    if extra_rules:
        txt += "\n" + extra_rules.strip() + "\n"
    return txt

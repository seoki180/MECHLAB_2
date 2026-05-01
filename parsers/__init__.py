from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterable
from typing import TypeAlias

from .base import BaseParser


ParserKey: TypeAlias = tuple[str, str]
REGISTRY: dict[ParserKey, type[BaseParser]] = {}


def _iter_parser_classes() -> Iterable[type[BaseParser]]:
    package_name = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name in {"base"}:
            continue
        module = importlib.import_module(f"{package_name}.{module_info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BaseParser:
                continue
            if issubclass(obj, BaseParser) and obj.__module__ == module.__name__:
                yield obj


def register(parser_cls: type[BaseParser]) -> type[BaseParser]:
    key = (parser_cls.maker, parser_cls.model)
    if key in REGISTRY:
        raise ValueError(f"Duplicate parser registration: {key}")
    REGISTRY[key] = parser_cls
    return parser_cls


def get_parser(maker: str, model: str, **kwargs) -> BaseParser:
    parser_cls = REGISTRY[(maker, model)]
    return parser_cls(**kwargs)


def makers() -> list[str]:
    return sorted({maker for maker, _ in REGISTRY})


def models_for(maker: str) -> list[str]:
    return [model for item_maker, model in sorted(REGISTRY) if item_maker == maker]


for _parser_cls in _iter_parser_classes():
    register(_parser_cls)


__all__ = ["BaseParser", "REGISTRY", "get_parser", "makers", "models_for", "register"]

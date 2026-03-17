from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Iterable

from deepcycle.data.registry import DatasetSpec


@dataclass(frozen=True)
class CustomAdapter:
    spec: DatasetSpec

    def iter_samples(self) -> Iterable[dict[str, Any]]:
        extra = self.spec.extra or {}
        module_name = extra.get("module")
        func_name = extra.get("function", "iter_samples")
        if not module_name:
            raise ValueError("custom adapter requires spec.extra.module (python module path)")

        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name, None)
        if fn is None:
            raise ValueError(f"custom adapter function not found: {module_name}.{func_name}")

        # The function receives the DatasetSpec and must yield dict samples with at least {"path": "..."}.
        yield from fn(self.spec)

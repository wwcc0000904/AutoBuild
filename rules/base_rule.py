from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class BaseRule(ABC):
    @abstractmethod
    def apply(self, project_root: Path) -> List[Path]:
        raise NotImplementedError

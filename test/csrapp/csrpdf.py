"""The part of the CSR app's csrpdf.py that documenso.py uses: a field's place on the page."""
from __future__ import annotations

from dataclasses import dataclass

PAGE_W, PAGE_H = 612.0, 792.0


@dataclass
class Field:
    page: int          # 1-based
    x: float
    top: float
    w: float
    h: float

    def percent(self) -> dict:
        return {"page": self.page, "positionX": round(self.x / PAGE_W * 100, 3),
                "positionY": round(self.top / PAGE_H * 100, 3),
                "width": round(self.w / PAGE_W * 100, 3), "height": round(self.h / PAGE_H * 100, 3)}

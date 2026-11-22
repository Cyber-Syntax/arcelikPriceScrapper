from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator


class ProductRow(BaseModel):
    name: str
    product_id: str = ""
    category: str | None = None
    price: Decimal | None = None
    discounted_price: Decimal | None = None
    kind: str = "product"  # product | warranty | explicit
    code: str = ""
    title: str = ""
    url: str = ""
    category_path: str = ""
    source: str = ""
    scraped_at: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("empty product name")
        return v

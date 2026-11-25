from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


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
    features: list[dict[str, str]] = Field(default_factory=list)
    specifications: list[dict[str, str]] = Field(default_factory=list)
    specs_scraped_at: str = ""
    scraped_at: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("empty product name")
        return v

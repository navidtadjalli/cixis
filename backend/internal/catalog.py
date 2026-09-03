"""Read-only active-menu snapshots from a verified CiXiS profile."""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from pos.internal_bridge import open_catalog_readonly

from internal.compatibility import CixisProfile, verify_cixis_profile


@dataclass(frozen=True)
class CatalogProduct:
    source_product_id: int
    source_category_id: int
    category_name: str
    name: str
    price: int
    is_available: bool
    category_monthly_quota: int
    product_monthly_quota: int


class CatalogReader:
    """A verified CiXiS catalog connection that cannot mutate its source."""

    def __init__(self, profile: CixisProfile) -> None:
        verify_cixis_profile(profile)
        self.connection = open_catalog_readonly(profile.database_path)

    def close(self) -> None:
        self.connection.close()

    def active_products(self) -> tuple[CatalogProduct, ...]:
        try:
            rows = self.connection.execute(
                """
                SELECT product.id, category.id, category.name, product.name,
                       product.price, product.is_available,
                       category.staff_free_monthly_quota,
                       product.staff_free_monthly_quota
                FROM pos_product AS product
                JOIN pos_category AS category ON category.id = product.category_id
                WHERE product.is_active = 1 AND category.is_active = 1
                ORDER BY category.sort_order, category.id, product.sort_order, product.id
                """
            ).fetchall()
        except sqlite3.Error as error:
            raise RuntimeError("CiXiS catalog is unavailable") from error
        return tuple(
            CatalogProduct(
                source_product_id=row[0],
                source_category_id=row[1],
                category_name=row[2],
                name=row[3],
                price=row[4],
                is_available=bool(row[5]),
                category_monthly_quota=row[6],
                product_monthly_quota=row[7],
            )
            for row in rows
        )

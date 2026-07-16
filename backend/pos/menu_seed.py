"""Shared menu seeding: load a bundled menu JSON into Category + Product rows.

Used by the ``seed_menu`` command (first launch) and by the setup screen's
load-menu button. Idempotent: rows match on category name + product name, so
re-running adds what is missing and never duplicates.
"""
import json
from pathlib import Path

from django.conf import settings

from .models import AppSetting, Category, Product


def menu_path(filename: str = "menu.json") -> Path:
    """Resolve a bundled seed file.

    ``BASE_DIR.parent`` is the repo root in dev and ``resources/`` in the
    packaged app, where electron-builder drops the seed JSON next to the backend
    dir. A new seed file must be added to extraResources in *both*
    electron-builder configs or it will be missing from installed builds.
    """
    return settings.BASE_DIR.parent / filename


def seed_menu(data: dict) -> dict:
    """Create any categories/products from ``data`` that aren't already there."""
    cat_created = prod_created = 0

    for cat_index, cat in enumerate(data.get("categories", [])):
        category, made = Category.objects.get_or_create(
            name=cat["name"],
            defaults={"sort_order": cat_index, "is_active": True},
        )
        if made:
            cat_created += 1
        elif category.sort_order != cat_index:
            # Keep ordering in sync without disturbing manual edits to flags.
            category.sort_order = cat_index
            category.save(update_fields=["sort_order"])

        for prod_index, item in enumerate(cat.get("items", [])):
            _, p_made = Product.objects.get_or_create(
                category=category,
                name=item["name"],
                defaults={
                    "description": item.get("description", ""),
                    "price": int(item.get("price", 0)),
                    "sort_order": prod_index,
                    "is_active": True,
                    "is_available": True,
                },
            )
            if p_made:
                prod_created += 1

    # The Electron shell reads this to decide whether first launch still needs a
    # seed; loading a menu by hand counts, so it never re-seeds over the top.
    AppSetting.objects.update_or_create(key="menu_seeded", defaults={"value": "true"})
    return {"categories_created": cat_created, "products_created": prod_created}


def seed_menu_from_file(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return seed_menu(json.load(fh))

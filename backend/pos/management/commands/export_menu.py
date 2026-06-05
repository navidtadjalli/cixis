"""Export the live Category + Product data back to the project-root menu.json.

Inverse of ``seed_menu``: it snapshots the current in-app menu so those values
become the initial seed data for fresh installs. Only active rows are written,
ordered by sort_order. Run against the live DB via the ``CIXIS_DB_PATH`` env var.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from pos.models import Category, Product


class Command(BaseCommand):
    help = "Write active categories and products to menu.json (initial seed data)."

    def handle(self, *args, **options):
        menu_path = settings.BASE_DIR.parent / "menu.json"

        categories = []
        for category in Category.objects.filter(is_active=True).order_by(
            "sort_order", "id"
        ):
            items = [
                {"name": product.name, "price": int(product.price)}
                for product in category.products.filter(is_active=True).order_by(
                    "sort_order", "id"
                )
            ]
            categories.append({"name": category.name, "items": items})

        with open(menu_path, "w", encoding="utf-8") as fh:
            fh.write(self._render(categories))

        product_count = sum(len(cat["items"]) for cat in categories)
        self._notify(menu_path, categories, product_count)

    @staticmethod
    def _render(categories) -> str:
        """Render menu.json with compact one-line items to match the hand-written style."""
        cat_blocks = []
        for cat in categories:
            item_lines = [
                '        {{ "name": {name}, "price": {price} }}'.format(
                    name=json.dumps(item["name"], ensure_ascii=False),
                    price=item["price"],
                )
                for item in cat["items"]
            ]
            items = ",\n".join(item_lines)
            name = json.dumps(cat["name"], ensure_ascii=False)
            cat_blocks.append(
                f'    {{\n      "name": {name},\n      "items": [\n{items}\n      ]\n    }}'
            )
        body = ",\n".join(cat_blocks)
        return f'{{\n  "categories": [\n{body}\n  ]\n}}\n'

    def _notify(self, menu_path, categories, product_count):
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(categories)} categories, {product_count} products "
                f"to {menu_path}."
            )
        )

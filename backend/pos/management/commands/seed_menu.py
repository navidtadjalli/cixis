"""Seed Category + Product records from the project-root menu.json.

Idempotent: re-running never duplicates rows (matched by category name + product
name). sort_order follows the JSON array index. After seeding, the AppSetting
``menu_seeded=true`` flag is set so the Electron shell only seeds on first launch.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pos.models import AppSetting, Category, Product


class Command(BaseCommand):
    help = "Load categories and products from menu.json into the local SQLite database."

    def handle(self, *args, **options):
        menu_path = settings.BASE_DIR.parent / "menu.json"
        if not menu_path.exists():
            raise CommandError(f"menu.json not found at {menu_path}")

        with open(menu_path, encoding="utf-8") as fh:
            data = json.load(fh)

        categories = data.get("categories", [])
        cat_created = prod_created = 0

        for cat_index, cat in enumerate(categories):
            category, made = Category.objects.get_or_create(
                name=cat["name"],
                defaults={"sort_order": cat_index, "is_active": True},
            )
            if made:
                cat_created += 1
            else:
                # Keep ordering in sync without disturbing manual edits to flags.
                if category.sort_order != cat_index:
                    category.sort_order = cat_index
                    category.save(update_fields=["sort_order"])

            for prod_index, item in enumerate(cat.get("items", [])):
                _, p_made = Product.objects.get_or_create(
                    category=category,
                    name=item["name"],
                    defaults={
                        "price": int(item.get("price", 0)),
                        "sort_order": prod_index,
                        "is_active": True,
                        "is_available": True,
                    },
                )
                if p_made:
                    prod_created += 1

        AppSetting.objects.update_or_create(
            key="menu_seeded", defaults={"value": "true"}
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: +{cat_created} categories, +{prod_created} products "
                f"({Category.objects.count()} categories, {Product.objects.count()} products total)."
            )
        )

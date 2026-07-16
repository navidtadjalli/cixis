"""Seed Category + Product records from the project-root menu.json.

Idempotent: re-running never duplicates rows (matched by category name + product
name). sort_order follows the JSON array index. After seeding, the AppSetting
``menu_seeded=true`` flag is set so the Electron shell only seeds on first launch.

The seeding itself lives in ``pos.menu_seed``, shared with the setup screen's
load-menu button.
"""
from django.core.management.base import BaseCommand, CommandError

from pos import menu_seed
from pos.models import Category, Product


class Command(BaseCommand):
    help = "Load categories and products from menu.json into the local SQLite database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="menu.json",
            help="Seed file to load, resolved next to the backend dir (default: menu.json).",
        )

    def handle(self, *args, **options):
        path = menu_seed.menu_path(options["file"])
        if not path.exists():
            raise CommandError(f"{options['file']} not found at {path}")

        result = menu_seed.seed_menu_from_file(path)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: +{result['categories_created']} categories, "
                f"+{result['products_created']} products "
                f"({Category.objects.count()} categories, "
                f"{Product.objects.count()} products total)."
            )
        )

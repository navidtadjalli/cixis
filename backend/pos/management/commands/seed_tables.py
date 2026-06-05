"""Seed Table records from the project-root tables.json.

Idempotent: re-running never duplicates rows (matched by name). sort_order
follows the JSON array index. After seeding, the AppSetting ``tables_seeded=true``
flag is set so the Electron shell only seeds on first launch.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pos.models import AppSetting, Table


class Command(BaseCommand):
    help = "Load the predefined table list from tables.json into the local SQLite database."

    def handle(self, *args, **options):
        tables_path = settings.BASE_DIR.parent / "tables.json"
        if not tables_path.exists():
            raise CommandError(f"tables.json not found at {tables_path}")

        with open(tables_path, encoding="utf-8") as fh:
            data = json.load(fh)

        names = [str(n).strip() for n in data.get("tables", []) if str(n).strip()]
        created = 0

        for index, name in enumerate(names):
            table, made = Table.objects.get_or_create(
                name=name,
                defaults={"sort_order": index, "is_active": True},
            )
            if made:
                created += 1
            elif table.sort_order != index:
                table.sort_order = index
                table.save(update_fields=["sort_order"])

        # Authoritative: the table set is exactly tables.json. Any row not listed
        # is removed so a fresh install matches the file with no manual cleanup.
        # Order.table is on_delete=SET_NULL, so removing a table never deletes orders.
        removed, _ = Table.objects.exclude(name__in=names).delete()

        AppSetting.objects.update_or_create(
            key="tables_seeded", defaults={"value": "true"}
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: +{created} created, -{removed} removed "
                f"({Table.objects.count()} tables total)."
            )
        )

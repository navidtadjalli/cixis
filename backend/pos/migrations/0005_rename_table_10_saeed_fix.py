from django.db import migrations

# Migration 0004 targeted the literal name "10", but the stored name is the
# Persian "میز ۱۰", so it matched nothing. Rename the real value here.
OLD_NAME = "میز ۱۰"
NEW_NAME = "میز سعید"


def rename_table(apps, schema_editor):
    Table = apps.get_model("pos", "Table")
    Table.objects.filter(name=OLD_NAME).update(name=NEW_NAME)


def revert_table(apps, schema_editor):
    Table = apps.get_model("pos", "Table")
    Table.objects.filter(name=NEW_NAME).update(name=OLD_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0004_rename_table_10_to_saeed"),
    ]

    operations = [
        migrations.RunPython(rename_table, revert_table),
    ]

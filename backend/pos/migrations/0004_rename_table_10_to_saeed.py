from django.db import migrations


def rename_table(apps, schema_editor):
    Table = apps.get_model("pos", "Table")
    Table.objects.filter(name="10").update(name="saeed")


def revert_table(apps, schema_editor):
    Table = apps.get_model("pos", "Table")
    Table.objects.filter(name="saeed").update(name="10")


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0003_orderitem_paid_quantity"),
    ]

    operations = [
        migrations.RunPython(rename_table, revert_table),
    ]

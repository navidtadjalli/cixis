"""Hash any existing plaintext revenue_password value in place."""
from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations


def hash_revenue_password(apps, schema_editor):
    AppSetting = apps.get_model("pos", "AppSetting")
    try:
        setting = AppSetting.objects.get(key="revenue_password")
    except AppSetting.DoesNotExist:
        return
    if not setting.value:
        return
    try:
        identify_hasher(setting.value)
    except ValueError:
        # Not a recognised hash → it is plaintext; hash it.
        setting.value = make_password(setting.value)
        setting.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [("pos", "0001_initial")]
    operations = [
        migrations.RunPython(hash_revenue_password, migrations.RunPython.noop),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0015_staff_consumption_fractional_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffconsumption",
            name="shift",
            field=models.CharField(
                choices=[("morning", "۹ تا ۱۷"), ("evening", "۱۶ تا ۲۴")],
                default="morning",
                max_length=16,
            ),
        ),
    ]

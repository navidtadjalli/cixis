from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0014_staff_tracker_and_guest_codes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="staffconsumption",
            name="quantity",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=10),
        ),
        migrations.AlterField(
            model_name="staffconsumption",
            name="line_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]

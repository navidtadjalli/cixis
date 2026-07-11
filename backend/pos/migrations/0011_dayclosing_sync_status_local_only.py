from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0010_dayclosing_gross_sales"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dayclosing",
            name="sync_status",
            field=models.CharField(
                choices=[
                    ("pending", "در انتظار"),
                    ("synced", "همگام‌شده"),
                    ("failed", "ناموفق"),
                    ("local_only", "فقط محلی"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
    ]

# Generated manually for the remote QR menu project.

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CafeMenuSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cafe_slug", models.CharField(db_index=True, max_length=120)),
                ("payload", models.JSONField()),
                ("version", models.CharField(max_length=120)),
                ("published_at", models.DateTimeField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.CreateModel(
            name="DayClosingSyncRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cafe_slug", models.CharField(max_length=120)),
                ("payload", models.JSONField()),
                ("business_date", models.DateField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.AddIndex(
            model_name="cafemenusnapshot",
            index=models.Index(fields=["cafe_slug", "-received_at"], name="qrmenu_caf_cafe_sl_015550_idx"),
        ),
        migrations.AddIndex(
            model_name="dayclosingsyncrecord",
            index=models.Index(fields=["cafe_slug", "business_date"], name="qrmenu_day_cafe_sl_5dfbbb_idx"),
        ),
    ]

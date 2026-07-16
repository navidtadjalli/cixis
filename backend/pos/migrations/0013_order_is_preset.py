from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0012_product_is_publishable'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='is_preset',
            field=models.BooleanField(default=False),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0006_order_day_closing'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dayclosing',
            name='business_date',
            field=models.DateField(),
        ),
    ]

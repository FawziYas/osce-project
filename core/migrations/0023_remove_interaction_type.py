from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_production_indexes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='checklistitem',
            name='interaction_type',
        ),
        migrations.RemoveField(
            model_name='checklistlibrary',
            name='interaction_type',
        ),
    ]

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_add_can_delete_session_permission'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='exam',
            options={
                'permissions': [
                    ('can_change_exam_date', 'Can change exam date even when sessions are in progress'),
                ]
            },
        ),
    ]

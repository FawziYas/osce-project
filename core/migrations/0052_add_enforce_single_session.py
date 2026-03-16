from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_fix_rls_examiner_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='examiner',
            name='enforce_single_session',
            field=models.BooleanField(
                default=False,
                help_text='If enabled, this user cannot log in on a second device while their session is active.',
            ),
        ),
    ]

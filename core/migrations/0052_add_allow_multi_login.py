from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_fix_rls_examiner_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='examiner',
            name='allow_multi_login',
            field=models.BooleanField(
                default=False,
                help_text='Allow this user to have multiple simultaneous sessions (bypasses single-session enforcement).',
            ),
        ),
        # Back-fill: existing dry users should be exempt straight away
        migrations.RunSQL(
            sql="UPDATE examiners SET allow_multi_login = TRUE WHERE is_dry_user = TRUE;",
            reverse_sql="UPDATE examiners SET allow_multi_login = FALSE WHERE is_dry_user = TRUE;",
        ),
    ]

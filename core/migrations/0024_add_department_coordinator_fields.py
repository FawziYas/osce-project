from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_remove_interaction_type'),
    ]

    operations = [
        # 1. Create the Department table
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.IntegerField(blank=True, default=None, help_text='UTC Unix timestamp when created', null=True)),
                ('updated_at', models.IntegerField(blank=True, default=None, help_text='UTC Unix timestamp when last updated', null=True)),
                ('name', models.CharField(max_length=150, unique=True)),
                ('description', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Department',
                'verbose_name_plural': 'Departments',
                'db_table': 'departments',
                'ordering': ['name'],
            },
        ),

        # 2. Add coordinator_department FK to Examiner
        migrations.AddField(
            model_name='examiner',
            name='coordinator_department',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='coordinators',
                to='core.department',
                db_index=True,
            ),
        ),

        # 3. Add coordinator_position field to Examiner
        migrations.AddField(
            model_name='examiner',
            name='coordinator_position',
            field=models.CharField(
                blank=True,
                choices=[('head', 'Head'), ('rta', 'RTA')],
                default='',
                max_length=10,
            ),
        ),
    ]

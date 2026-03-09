"""
Backfill Course.department from the Exam.department text field.

For each Course, looks at the text in Exam.department, matches it
against Department.name, and sets Course.department_id accordingly.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Course = apps.get_model('core', 'Course')
    Department = apps.get_model('core', 'Department')
    Exam = apps.get_model('core', 'Exam')

    dept_map = {d.name.lower().strip(): d for d in Department.objects.all()}

    for course in Course.objects.filter(department__isnull=True):
        exam = Exam.objects.filter(course=course).first()
        if exam and exam.department:
            dept = dept_map.get(exam.department.lower().strip())
            if dept:
                course.department = dept
                course.save(update_fields=['department'])


def reverse(apps, schema_editor):
    # No-op reverse: don't blank out departments
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_add_department_to_course'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse, elidable=True),
    ]

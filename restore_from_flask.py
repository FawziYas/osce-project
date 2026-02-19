"""
Restore courses and ILOs from the old Flask database (osce_examiner.db) 
to the new Django database (db.sqlite3).

This script reads from the Flask database and uses Django ORM to insert
the data into the Django database.
"""
import os
import sys
import sqlite3
import django

# Fix Unicode encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings.development')
django.setup()

from core.models import Course, ILO

def restore_data():
    """Copy courses and ILOs from Flask database to Django database."""
    
    flask_db_path = r'C:\Users\M7md\Desktop\dev\OSCE_Exam_DEV\instance\osce_examiner.db'
    
    if not os.path.exists(flask_db_path):
        print(f"❌ Flask database not found at: {flask_db_path}")
        return False
    
    try:
        # Connect to Flask database
        flask_conn = sqlite3.connect(flask_db_path)
        flask_cursor = flask_conn.cursor()
        
        print("✓ Connected to Flask database")
        
        # ========== Restore Courses ==========
        print("\n📚 Restoring Courses...")
        flask_cursor.execute("SELECT id, code, name, short_code FROM courses")
        courses_data = flask_cursor.fetchall()
        
        print(f"Found {len(courses_data)} courses in Flask database")
        
        # Clear existing courses
        Course.objects.all().delete()
        print("Cleared existing courses")
        
        restored_count = 0
        for flask_id, code, name, short_code in courses_data:
            course = Course.objects.create(
                code=code,
                name=name,
                short_code=short_code or ''
            )
            restored_count += 1
            print(f"  ✓ Created course: [{code}] {name}")
        
        print(f"\n✓ Restored {restored_count} courses")
        
        # ========== Restore ILOs ==========
        print("\n🎯 Restoring ILOs...")
        flask_cursor.execute("SELECT id, course_id, number, description, theme_id FROM ilos")
        ilos_data = flask_cursor.fetchall()
        
        print(f"Found {len(ilos_data)} ILOs in Flask database")
        
        # Clear existing ILOs
        ILO.objects.all().delete()
        print("Cleared existing ILOs")
        
        # Build a map of Flask course IDs to Django courses
        flask_cursor.execute("SELECT id FROM courses")
        flask_course_ids = [row[0] for row in flask_cursor.fetchall()]
        
        django_courses = {i+1: course for i, course in enumerate(Course.objects.order_by('id'))}
        
        restored_ilo_count = 0
        for flask_id, flask_course_id, number, description, theme_id in ilos_data:
            # Map Flask course ID to Django course
            if flask_course_id in django_courses:
                course = django_courses[flask_course_id]
                ilo = ILO.objects.create(
                    course=course,
                    number=number,
                    description=description,
                    theme_id=theme_id or 1
                )
                restored_ilo_count += 1
                print(f"  ✓ Created ILO {number} for {course.code}: {description[:40]}...")
        
        print(f"\n✓ Restored {restored_ilo_count} ILOs")
        
        # ========== Summary ==========
        print("\n" + "="*60)
        print("✅ Flask→Django Restoration Complete!")
        print("="*60)
        
        # Show what was restored
        print(f"\nRestored Courses ({Course.objects.count()}):")
        for course in Course.objects.all().order_by('code'):
            ilo_count = ILO.objects.filter(course=course).count()
            print(f"  - [{course.code}] {course.name} ({ilo_count} ILOs)")
        
        print(f"\nTotal:")
        print(f"  - Courses: {Course.objects.count()}")
        print(f"  - ILOs: {ILO.objects.count()}")
        
        flask_conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import sys
    # Redirect output to file and console
    class TeeOutput:
        def __init__(self, *files):
            self.files = files
        def write(self, data):
            for f in self.files:
                f.write(data)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()
    
    with open('restore_output.txt', 'w', encoding='utf-8') as f:
        sys.stdout = TeeOutput(sys.stdout, f)
        sys.stderr = TeeOutput(sys.stderr, f)
        
        success = restore_data()
        
    sys.exit(0 if success else 1)

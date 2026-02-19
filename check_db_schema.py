import sqlite3

flask_db_path = r'C:\Users\M7md\Desktop\dev\OSCE_Exam_DEV\instance\osce_examiner.db'

conn = sqlite3.connect(flask_db_path)
cursor = conn.cursor()

# Get ilos table schema
print("ILOs table schema:")
cursor.execute("PRAGMA table_info(ilos)")
for row in cursor.fetchall():
    print(f"  {row}")

print("\nSample ILOs data:")
cursor.execute("SELECT * FROM ilos LIMIT 3")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()

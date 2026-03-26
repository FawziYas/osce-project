"""Transfer ownership of all public tables + sequences to osce_app."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings.production')
django.setup()
from django.db import connection

sql = """
DO $$
DECLARE
    tbl text;
    seq text;
BEGIN
    FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(tbl) || ' OWNER TO osce_app';
    END LOOP;
    FOR seq IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
        EXECUTE 'ALTER SEQUENCE public.' || quote_ident(seq) || ' OWNER TO osce_app';
    END LOOP;
END$$;
"""

with connection.cursor() as c:
    c.execute(sql)
print("Ownership of all tables and sequences transferred to osce_app.")

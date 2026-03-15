"""
Management command to verify that PostgreSQL Row-Level Security (RLS)
policies, helper functions, and table settings are all correctly applied
after running migrations on a production PostgreSQL database.

Usage:
    python manage.py verify_rls
    python manage.py verify_rls --quiet   # exit-code only (CI use)
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


EXPECTED_TABLES = [
    'departments', 'courses', 'exams', 'exam_sessions',
    'paths', 'stations', 'checklist_items',
    'examiner_assignments', 'station_scores', 'item_scores',
]

EXPECTED_FUNCTIONS = [
    'app_role', 'is_global_role', 'is_coordinator',
    'app_department_id', 'app_user_id', 'station_department_id',
    'examiner_has_station', 'exam_department_id',
    'session_department_id', 'path_department_id',
]

MIN_POLICY_COUNT = 40


class Command(BaseCommand):
    help = (
        'Verify that PostgreSQL RLS policies are correctly applied. '
        'Exits with code 1 if any check fails. No-op on SQLite.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress detailed output; only print summary and errors.',
        )

    def handle(self, *args, **options):
        quiet = options['quiet']
        vendor = connection.vendor

        if vendor != 'postgresql':
            self.stdout.write(
                self.style.WARNING(
                    f'Database vendor is "{vendor}" — RLS only applies to PostgreSQL. Skipping.'
                )
            )
            return

        failures = []

        # ── 1. Table RLS flags ────────────────────────────────────────────
        if not quiet:
            self.stdout.write('\n[1/3] Checking RLS flags on tables...')

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = ANY(%s)
                ORDER BY relname;
                """,
                [EXPECTED_TABLES],
            )
            rows = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        for table in EXPECTED_TABLES:
            if table not in rows:
                failures.append(f'  TABLE MISSING:  {table} not found in pg_class')
                continue
            rls_on, rls_forced = rows[table]
            if not rls_on:
                failures.append(f'  RLS NOT ENABLED:  {table}.relrowsecurity = false')
            if not rls_forced:
                failures.append(f'  RLS NOT FORCED:   {table}.relforcerowsecurity = false')
            elif not quiet:
                self.stdout.write(f'  OK  {table} (RLS on, forced)')

        # ── 2. Helper functions ───────────────────────────────────────────
        if not quiet:
            self.stdout.write('\n[2/3] Checking RLS helper functions...')

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT proname FROM pg_proc
                WHERE proname = ANY(%s)
                ORDER BY proname;
                """,
                [EXPECTED_FUNCTIONS],
            )
            found_functions = {row[0] for row in cursor.fetchall()}

        for fn in EXPECTED_FUNCTIONS:
            if fn not in found_functions:
                failures.append(f'  MISSING FUNCTION: {fn}()')
            elif not quiet:
                self.stdout.write(f'  OK  {fn}()')

        # ── 3. Policy count ───────────────────────────────────────────────
        if not quiet:
            self.stdout.write('\n[3/3] Counting policies in public schema...')

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename, policyname, cmd
                FROM pg_policies
                WHERE schemaname = 'public'
                ORDER BY tablename, policyname;
                """
            )
            policies = cursor.fetchall()

        policy_count = len(policies)
        if not quiet:
            for tablename, policyname, cmd in policies:
                self.stdout.write(f'  {tablename:<30} {cmd:<10} {policyname}')

        if policy_count < MIN_POLICY_COUNT:
            failures.append(
                f'  INSUFFICIENT POLICIES: found {policy_count}, expected >= {MIN_POLICY_COUNT}'
            )
        elif not quiet:
            self.stdout.write(f'\n  Total policies: {policy_count} (>= {MIN_POLICY_COUNT} required)')

        # ── Summary ───────────────────────────────────────────────────────
        self.stdout.write('')
        if failures:
            self.stdout.write(self.style.ERROR('RLS verification FAILED:'))
            for msg in failures:
                self.stdout.write(self.style.ERROR(msg))
            raise CommandError('One or more RLS checks failed. See output above.')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'All RLS checks passed: {len(EXPECTED_TABLES)} tables, '
                    f'{len(EXPECTED_FUNCTIONS)} functions, {policy_count} policies.'
                )
            )

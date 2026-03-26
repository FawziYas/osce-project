"""
Django admin registration for all core models.
"""
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
import logging

audit_logger = logging.getLogger('osce.audit')

# Customize Django admin site labels
admin.site.site_header = "OSCE Administration"
admin.site.site_title = "OSCE Administration"
admin.site.index_title = "OSCE Administration"

from .models import (
    Theme, Course, ILO, Exam, Station, ChecklistItem,
    ExamSession, SessionStudent, StationScore, ItemScore,
    Examiner, ExaminerAssignment, Path, ChecklistLibrary,
    StationVariant, TemplateLibrary, StationTemplate, AuditLog,
    AuditLogArchive,
    LoginAuditLog, UserSession, UserProfile, Department,
)


# ── Custom Form for Examiner to enforce role-specific constraints ──
class ExaminerAdminForm(forms.ModelForm):
    """Custom form for Examiner admin to validate coordinator constraints at form level."""

    class Meta:
        model = Examiner
        fields = ('username', 'email', 'full_name', 'title', 'role', 'department',
                  'coordinator_position', 'is_active', 'is_staff', 'is_superuser',
                  'groups', 'user_permissions', 'password')

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        department = cleaned_data.get('department')
        coordinator_position = cleaned_data.get('coordinator_position')

        # Enforce coordinator constraints at form level
        if role == Examiner.ROLE_COORDINATOR:
            if not department:
                raise forms.ValidationError(
                    'Coordinators must be assigned to a department.'
                )
            if not coordinator_position:
                raise forms.ValidationError(
                    'Coordinators must have a coordinator position selected.'
                )

        # Enforce non-coordinator constraint
        if role != Examiner.ROLE_COORDINATOR and coordinator_position:
            raise forms.ValidationError(
                'Only coordinators can have a coordinator position.'
            )

        return cleaned_data


# ── User Profiles (default-password / forced-change tracking) ────
# ── User Profile Inline (embedded inside ExaminerAdmin) ─────────
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = 'Password & Profile'
    verbose_name_plural = 'Password & Profile'
    readonly_fields = ('password_changed_at',)
    fields = ('must_change_password', 'password_changed_at')


# ── Active User Sessions ─────────────────────────────────────────
@admin.action(description='End selected sessions')
def end_sessions(modeladmin, request, queryset):
    """Delete Django session records and UserSession rows for selected entries."""
    count = 0
    keys = []
    for us in queryset:
        keys.append(us.session_key[:8])
        us.kill_session()  # deletes both Django session + UserSession row
        count += 1
    audit_logger.warning(
        'ADMIN: ended %d session(s) for [%s] by %s',
        count, ', '.join(keys), request.user.username
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'created_at', 'last_activity_display', 'idle_minutes_display', 'session_status')
    list_filter = ('user', 'created_at')
    search_fields = ('user__username', 'session_key')
    readonly_fields = ('user', 'session_key', 'created_at')
    actions = [end_sessions]
    ordering = ('-created_at',)

    def _get_last_activity(self, obj):
        """Fetch _last_activity timestamp from the session store. Returns None if unavailable."""
        import time
        from importlib import import_module
        from django.conf import settings as _s
        try:
            engine = import_module(_s.SESSION_ENGINE)
            store = engine.SessionStore(session_key=obj.session_key)
            data = store.load()
            ts = data.get('_last_activity')
            return float(ts) if ts else None
        except Exception:
            return None

    @admin.display(description='Last Activity')
    def last_activity_display(self, obj):
        import datetime, time
        ts = self._get_last_activity(obj)
        if ts is None:
            return '—'
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        from django.utils.timezone import localtime
        from django.utils import timezone
        local_dt = localtime(dt)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='Idle (min)')
    def idle_minutes_display(self, obj):
        import time
        ts = self._get_last_activity(obj)
        if ts is None:
            return '—'
        idle_seconds = time.time() - ts
        minutes = int(idle_seconds / 60)
        seconds = int(idle_seconds % 60)
        if minutes == 0:
            return f'{seconds}s'
        return f'{minutes}m {seconds}s'

    @admin.display(description='Status')
    def session_status(self, obj):
        return '✅ Active' if obj.is_session_alive() else '❌ Expired'

    def has_add_permission(self, request):
        return False  # Sessions are created by the login flow only

    def delete_model(self, request, obj):
        """Ensure Django Session in the store is also purged."""
        obj.kill_session()


# ── Custom User Admin ─────────────────────────────────────────────
@admin.action(description='🔑 Reset selected users to default password')
def reset_examiner_password(modeladmin, request, queryset):
    """Reset password to DEFAULT_USER_PASSWORD and flag must_change_password on the linked UserProfile."""
    from django.conf import settings as _settings

    if not request.user.is_superuser:
        modeladmin.message_user(request, 'Only superusers can reset passwords.', level='ERROR')
        return

    default_pw = getattr(_settings, 'DEFAULT_USER_PASSWORD', '12345678F')
    count = 0
    for examiner in queryset:
        examiner.set_password(default_pw)
        examiner.save(update_fields=['password'])
        # Mark the linked UserProfile so the user is forced to change on next login
        try:
            profile = examiner.profile
            profile.must_change_password = True
            profile.password_changed_at = None
            profile.save(update_fields=['must_change_password', 'password_changed_at'])
        except Exception:
            pass  # Profile may not exist yet
        audit_logger.warning(
            "Admin '%s' reset password for examiner '%s'.",
            request.user.username, examiner.username,
        )
        count += 1
    modeladmin.message_user(request, f'{count} user(s) reset to default password and marked must change password.')


@admin.register(Examiner)
class ExaminerAdmin(BaseUserAdmin):
    form = ExaminerAdminForm
    list_display = ('username', 'email', 'full_name', 'role', 'title', 'department', 'is_active', 'get_must_change_password', 'is_deleted', 'is_staff')
    list_filter = ('role', 'is_active', 'is_deleted', 'is_staff', 'department')
    search_fields = ('username', 'email', 'full_name')
    ordering = ('username',)
    actions = [reset_examiner_password]
    inlines = [UserProfileInline]
    readonly_fields = ('reset_password_button',)

    # Override the admin display name to "Users Profiles"
    class Meta:
        verbose_name = 'Users Profile'
        verbose_name_plural = 'Users Profiles'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'title', 'department', 'coordinator_position')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Session & Access', {'fields': ('is_dry_user', 'allow_multi_login')}),
        ('Password Reset', {'fields': ('reset_password_button',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'full_name', 'role', 'password1', 'password2'),
        }),
        ('Department & Position', {
            'classes': ('wide',),
            'fields': ('department', 'coordinator_position'),
            'description': 'Coordinators must have a department assigned and a coordinator position selected.',
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/reset-default-password/',
                self.admin_site.admin_view(self.reset_default_password_view),
                name='core_examiner_reset_default_password',
            ),
        ]
        return custom + urls

    def reset_default_password_view(self, request, pk):
        """Handle the reset-to-default-password button from the detail page."""
        from django.conf import settings as _settings
        from django.contrib import messages

        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can reset passwords.')
            return HttpResponseRedirect(reverse('admin:core_examiner_change', args=[pk]))

        try:
            examiner = Examiner.objects.get(pk=pk)
        except Examiner.DoesNotExist:
            messages.error(request, 'User not found.')
            return HttpResponseRedirect(reverse('admin:core_examiner_changelist'))

        default_pw = getattr(_settings, 'DEFAULT_USER_PASSWORD', '12345678F')
        examiner.set_password(default_pw)
        examiner.save(update_fields=['password'])

        try:
            profile = examiner.profile
            profile.must_change_password = True
            profile.password_changed_at = None
            profile.save(update_fields=['must_change_password', 'password_changed_at'])
        except Exception:
            pass

        audit_logger.warning(
            "Admin '%s' reset password for examiner '%s' via detail page.",
            request.user.username, examiner.username,
        )
        messages.success(
            request,
            f"Password for '{examiner.username}' reset to default. They will be forced to change it on next login."
        )
        return HttpResponseRedirect(reverse('admin:core_examiner_change', args=[pk]))

    @admin.display(description='Reset Password')
    def reset_password_button(self, obj):
        if not obj or not obj.pk:
            return '—'
        url = reverse('admin:core_examiner_reset_default_password', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background:#ba2121;color:#fff;'
            'padding:6px 14px;border-radius:4px;text-decoration:none;font-weight:bold;"'
            ' onclick="return confirm(\'Reset password for {} to the default password and mark must change?\');">'
            '🔑 Reset to Default Password</a>',
            url, obj.username,
        )

    @admin.display(description='Must Change PW?', boolean=True)
    def get_must_change_password(self, obj):
        try:
            return obj.profile.must_change_password
        except Exception:
            return None

    def get_inlines(self, request, obj):
        """Only show UserProfileInline on the change view (profile doesn't exist yet on add)."""
        if obj is None:  # add view
            return []
        return self.inlines

    def has_delete_permission(self, request, obj=None):
        """Only superuser and admin can delete examiners."""
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            return False
        return super().has_delete_permission(request, obj)


# ── Theme ──────────────────────────────────────────────────────────
@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'color', 'display_order', 'active')
    list_editable = ('display_order', 'active')
    ordering = ('display_order',)


# ── Course / ILO ──────────────────────────────────────────────────
class ILOInline(admin.TabularInline):
    model = ILO
    extra = 0
    fields = ('number', 'description', 'osce_marks', 'theme')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'short_code', 'name', 'year_level')
    list_filter = ('year_level',)
    search_fields = ('code', 'short_code', 'name')
    inlines = [ILOInline]


@admin.register(ILO)
class ILOAdmin(admin.ModelAdmin):
    list_display = ('number', 'course', 'theme', 'osce_marks')
    list_filter = ('course', 'theme')



# ── Exam / Station / ChecklistItem ───────────────────────────────
class StationInline(admin.TabularInline):
    model = Station
    extra = 0
    fields = ('station_number', 'name', 'duration_minutes', 'active')
    readonly_fields = ('id',)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'exam_date', 'status', 'is_deleted')
    list_filter = ('status', 'is_deleted', 'course')
    search_fields = ('name',)
    inlines = [StationInline]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0
    fields = ('item_number', 'description', 'points', 'rubric_type')


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('station_number', 'name', 'path', 'duration_minutes', 'active')
    list_filter = ('active', 'is_deleted')
    search_fields = ('name',)
    inlines = [ChecklistItemInline]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('item_number', 'description', 'station', 'points')


def _get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        ip = x_forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    # Strip port if present (e.g., Azure proxy sends "IP:PORT")
    if ip and ':' in ip and '.' in ip:
        ip = ip.rsplit(':', 1)[0]
    return ip


def revert_to_scheduled(modeladmin, request, queryset):
    """Admin action: revert finished/completed sessions back to scheduled."""
    # Permission check: superuser or has can_revert_session permission
    if not (request.user.is_superuser or request.user.has_perm('core.can_revert_session')):
        modeladmin.message_user(
            request,
            'You do not have permission to revert sessions.',
            level='error',
        )
        return

    reverted = 0
    skipped = 0
    ip_address = _get_client_ip(request)

    for session in queryset.select_for_update():
        previous_status = session.status
        if previous_status == 'completed' and not request.user.is_superuser:
            skipped += 1
            modeladmin.message_user(
                request,
                f'Skipped "{session.name}" – reverting completed sessions requires superuser.',
                level='warning',
            )
            continue
        if previous_status not in ('finished', 'completed'):
            skipped += 1
            modeladmin.message_user(
                request,
                f'Skipped "{session.name}" – status is "{previous_status}", not "finished" or "completed".',
                level='warning',
            )
            continue

        session.status = 'scheduled'
        session.save(update_fields=['status', 'updated_at'])
        reverted += 1

        audit_logger.info(
            'SESSION_REVERT | admin=%s | session_id=%s | '
            'previous_status=%s | new_status=scheduled | ip=%s',
            request.user.username,
            session.id,
            previous_status,
            ip_address,
        )

    if reverted:
        modeladmin.message_user(
            request,
            f'Successfully reverted {reverted} session(s) to "scheduled".',
            level='success',
        )


revert_to_scheduled.short_description = 'Revert to Scheduled (completed → scheduled)'


# ── Session ──────────────────────────────────────────────────────
@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam', 'session_date', 'session_type', 'status')
    list_filter = ('status', 'session_type')
    search_fields = ('name',)
    actions = [revert_to_scheduled]


@admin.register(SessionStudent)
class SessionStudentAdmin(admin.ModelAdmin):
    list_display = ('student_number', 'full_name', 'session', 'path', 'status')
    list_filter = ('status',)
    search_fields = ('student_number', 'full_name')


# ── Scoring ──────────────────────────────────────────────────────
@admin.register(StationScore)
class StationScoreAdmin(admin.ModelAdmin):
    list_display = ('session_student', 'station', 'examiner', 'total_score', 'status', 'sync_status')
    list_filter = ('status', 'sync_status')


@admin.register(ItemScore)
class ItemScoreAdmin(admin.ModelAdmin):
    list_display = ('checklist_item', 'station_score', 'score', 'max_points')


# ── Paths ────────────────────────────────────────────────────────
@admin.register(Path)
class PathAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'rotation_minutes', 'is_active')
    list_filter = ('is_active', 'is_deleted')


@admin.register(ExaminerAssignment)
class ExaminerAssignmentAdmin(admin.ModelAdmin):
    list_display = ('examiner', 'station', 'session')
    list_filter = ('session',)


# ── Library ──────────────────────────────────────────────────────
@admin.register(ChecklistLibrary)
class ChecklistLibraryAdmin(admin.ModelAdmin):
    list_display = ('id', 'ilo', 'description', 'suggested_points', 'usage_count', 'active')
    list_filter = ('active',)


# ── Variants / Templates ────────────────────────────────────────
@admin.register(StationVariant)
class StationVariantAdmin(admin.ModelAdmin):
    list_display = ('station', 'exam_session')


@admin.register(TemplateLibrary)
class TemplateLibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam', 'is_active', 'display_order')


@admin.register(StationTemplate)
class StationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam', 'library', 'is_active', 'display_order')


# ── Audit Log ───────────────────────────────────────────────────

import csv
import io
import json as _json
from django.http import StreamingHttpResponse
from django.utils.safestring import mark_safe


class _Echo:
    """Pseudo-buffer for StreamingHttpResponse CSV writer."""
    def write(self, value):
        return value


def _export_audit_csv(modeladmin, request, queryset):
    """
    Stream-export selected audit log rows as CSV.
    Logs the export action itself to the audit trail.
    """
    from core.utils.audit import AuditLogService
    from core.models.audit import REPORT_EXPORTED

    pseudo_buf = _Echo()
    writer = csv.writer(pseudo_buf)

    header = [
        'timestamp', 'user_email', 'username', 'user_role', 'department_id',
        'action', 'status', 'resource_type', 'resource_label', 'resource_id',
        'old_value', 'new_value', 'ip_address', 'user_agent', 'description',
    ]

    def rows():
        yield writer.writerow(header)
        for obj in queryset.iterator(chunk_size=500):
            yield writer.writerow([
                obj.timestamp.isoformat() if obj.timestamp else '',
                getattr(obj.user, 'email', '') if obj.user else '',
                obj.username,
                obj.user_role,
                obj.department_id or '',
                obj.action,
                obj.status,
                obj.resource_type,
                obj.resource_label,
                obj.resource_id,
                _json.dumps(obj.old_value) if obj.old_value else '',
                _json.dumps(obj.new_value) if obj.new_value else '',
                obj.ip_address or '',
                obj.user_agent[:120] if obj.user_agent else '',
                obj.description[:200] if obj.description else '',
            ])

    response = StreamingHttpResponse(rows(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'

    # Log the export itself
    AuditLogService.log(
        action=REPORT_EXPORTED,
        user=request.user,
        request=request,
        resource_type='AuditLog',
        resource_label_override='CSV Export',
        description=f'Exported {queryset.count()} audit log rows',
        extra={'row_count': queryset.count(), 'format': 'CSV'},
    )

    return response


_export_audit_csv.short_description = 'Export selected as CSV'


def _export_audit_json(modeladmin, request, queryset):
    """Stream-export selected audit log rows as JSON."""
    from core.utils.audit import AuditLogService
    from core.models.audit import REPORT_EXPORTED

    def rows():
        yield '['
        first = True
        for obj in queryset.iterator(chunk_size=500):
            entry = {
                'timestamp': obj.timestamp.isoformat() if obj.timestamp else '',
                'username': obj.username,
                'user_role': obj.user_role,
                'department_id': obj.department_id,
                'action': obj.action,
                'status': obj.status,
                'resource_type': obj.resource_type,
                'resource_label': obj.resource_label,
                'resource_id': obj.resource_id,
                'old_value': obj.old_value,
                'new_value': obj.new_value,
                'ip_address': obj.ip_address,
                'description': obj.description,
            }
            if not first:
                yield ','
            yield _json.dumps(entry)
            first = False
        yield ']'

    response = StreamingHttpResponse(rows(), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.json"'

    AuditLogService.log(
        action=REPORT_EXPORTED,
        user=request.user,
        request=request,
        resource_type='AuditLog',
        resource_label_override='JSON Export',
        description=f'Exported {queryset.count()} audit log rows',
        extra={'row_count': queryset.count(), 'format': 'JSON'},
    )

    return response


_export_audit_json.short_description = 'Export selected as JSON'


def _admin_archive_old_logs(modeladmin, request, queryset):
    """
    Admin action: archive all audit logs older than 90 days.
    The queryset selection is intentionally ignored — this always
    archives everything beyond the cutoff, not just selected rows.
    Only superusers may trigger this.
    """
    from django.contrib import messages
    from core.tasks import archive_old_audit_logs
    from core.utils.audit import AuditLogService
    from core.models.audit import ADMIN_ACTION

    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            'Only superusers can trigger log archival.',
            level=messages.ERROR,
        )
        return

    try:
        result = archive_old_audit_logs.delay(days=90, batch_size=2000)
        AuditLogService.log(
            action=ADMIN_ACTION,
            user=request.user,
            request=request,
            resource_type='AuditLog',
            description='Manual archive of audit logs older than 90 days queued via admin action',
        )
        modeladmin.message_user(
            request,
            f'Archival task queued (task id: {result.id}). '
            'Logs older than 90 days will be moved to the archive table in the background.',
            level=messages.SUCCESS,
        )
    except Exception:
        # Celery not available — run synchronously
        from core.management.commands.archive_old_logs import Command
        cmd = Command()
        cmd.stdout = type('_W', (), {'write': lambda self, msg: None})()
        cmd.style = type('_S', (), {
            'SUCCESS': lambda self, m: m,
            'WARNING': lambda self, m: m,
        })()
        cmd.handle(days=90, batch_size=2000, dry_run=False)
        modeladmin.message_user(
            request,
            'Archival completed synchronously (Celery not available). '
            'Logs older than 90 days have been moved to the archive table.',
            level=messages.SUCCESS,
        )


_admin_archive_old_logs.short_description = 'Archive logs older than 90 days (superuser only)'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Full-featured audit log viewer.

    - Read-only, non-editable, non-deletable
    - Role-scoped queryset (Coordinator sees own dept only, Examiner blocked)
    - JSON diff widget for old_value / new_value
    - CSV and JSON streaming exports
    - Anomaly flags for suspicious patterns
    - Checksum verification display
    - Manual archive trigger (button + action, superuser only)
    """
    change_list_template = 'admin/core/auditlog/change_list.html'

    list_display = (
        'timestamp', 'username', 'user_role', 'department_id',
        'action', 'resource_type', 'resource_label', 'status',
        'ip_address', 'anomaly_flag', 'checksum_status',
    )
    list_filter = (
        'action', 'user_role', 'resource_type', 'status',
        'department_id',
    )
    search_fields = (
        'username', 'resource_label', 'resource_id', 'ip_address',
        'description',
    )
    readonly_fields = (
        'id', 'timestamp', 'user', 'username', 'user_role',
        'department_id', 'action', 'status',
        'resource_type', 'resource_id', 'resource_label',
        'formatted_old_value', 'formatted_new_value', 'formatted_diff',
        'description', 'ip_address', 'user_agent',
        'request_method', 'request_path', 'extra_data',
        'checksum', 'checksum_status',
    )
    list_per_page = 50
    list_select_related = ('user',)
    actions = [_export_audit_csv, _export_audit_json, _admin_archive_old_logs]
    ordering = ('-timestamp',)

    fieldsets = (
        ('When & Who', {
            'fields': (
                'id', 'timestamp', 'user', 'username', 'user_role',
                'department_id',
            ),
        }),
        ('What Happened', {
            'fields': ('action', 'status', 'description'),
        }),
        ('Resource', {
            'fields': (
                'resource_type', 'resource_id', 'resource_label',
            ),
        }),
        ('Change Details', {
            'classes': ('collapse',),
            'fields': (
                'formatted_old_value', 'formatted_new_value',
                'formatted_diff',
            ),
        }),
        ('Request Context', {
            'classes': ('collapse',),
            'fields': (
                'ip_address', 'user_agent', 'request_method',
                'request_path', 'extra_data',
            ),
        }),
        ('Integrity', {
            'classes': ('collapse',),
            'fields': ('checksum', 'checksum_status'),
        }),
    )

    def formatted_old_value(self, obj):
        return self._format_json(obj.old_value)
    formatted_old_value.short_description = 'Old Value (JSON)'

    def formatted_new_value(self, obj):
        return self._format_json(obj.new_value)
    formatted_new_value.short_description = 'New Value (JSON)'

    def formatted_diff(self, obj):
        """Show a side-by-side diff of old_value → new_value."""
        if not obj.old_value or not obj.new_value:
            return mark_safe('<em>N/A (not an update action)</em>')

        rows = []
        all_keys = sorted(set(list(obj.old_value.keys()) + list(obj.new_value.keys())))
        for key in all_keys:
            old = obj.old_value.get(key, '—')
            new = obj.new_value.get(key, '—')
            if old != new:
                rows.append(
                    f'<tr style="background:#fff3cd">'
                    f'<td><strong>{key}</strong></td>'
                    f'<td style="color:#842029">{old}</td>'
                    f'<td style="color:#0f5132">{new}</td>'
                    f'</tr>'
                )
            else:
                rows.append(
                    f'<tr><td>{key}</td><td>{old}</td><td>{new}</td></tr>'
                )

        table = (
            '<table style="border-collapse:collapse;width:100%">'
            '<thead><tr><th>Field</th><th>Old</th><th>New</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table>'
        )
        return mark_safe(table)
    formatted_diff.short_description = 'Change Diff'

    def anomaly_flag(self, obj):
        """Flag suspicious entries: failed status, security actions, or unusual patterns."""
        flags = []
        if obj.status in ('FAILED', 'BLOCKED'):
            flags.append('⚠️')
        if obj.action in (
            'UNAUTHORIZED_ACCESS', 'SUSPICIOUS_ACTIVITY',
            'RATE_LIMIT_HIT', 'TOKEN_VALIDATION_FAILED',
        ):
            flags.append('🚨')
        extra = obj.extra_data or {}
        if extra.get('amendment_count', 0) >= 3:
            flags.append('🔄')
        return ' '.join(flags) if flags else '✓'
    anomaly_flag.short_description = 'Flags'

    def checksum_status(self, obj):
        """Show whether the checksum is valid for this record."""
        if not obj.checksum:
            return format_html('<span style="color:gray">—</span>')
        if obj.verify_checksum():
            return format_html('<span style="color:green">✓ Valid</span>')
        return format_html('<span style="color:red;font-weight:bold">✗ TAMPERED</span>')
    checksum_status.short_description = 'Integrity'

    @staticmethod
    def _format_json(data):
        if not data:
            return mark_safe('<em>—</em>')
        formatted = _json.dumps(data, indent=2, ensure_ascii=False, default=str)
        return mark_safe(f'<pre style="max-height:300px;overflow:auto">{formatted}</pre>')

    # ── Access control ───────────────────────────────────────────

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        """
        - Superuser: full access
        - Admin: access (filtered in get_queryset)
        - Coordinator: access (scoped to own department)
        - Examiner: NO access
        """
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        role = getattr(user, 'role', '')
        return role in ('admin', 'coordinator')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user

        if user.is_superuser:
            return qs

        role = getattr(user, 'role', '')

        if role == 'admin':
            # Admins see all logs EXCEPT login/admin events of other admins/superusers
            return qs.exclude(
                action__in=['LOGIN_SUCCESS', 'LOGIN_FAILED', 'ADMIN_ACTION'],
                user_role__in=['superuser', 'admin'],
            ).exclude(
                action__in=['LOGIN_SUCCESS', 'LOGIN_FAILED', 'ADMIN_ACTION'],
                user=None,  # keep anonymous attempts visible
            ) | qs.filter(user=user)

        if role == 'coordinator':
            # Coordinator sees only their own department
            dept = getattr(user, 'department', None)
            if dept:
                return qs.filter(department_id=dept.pk)
            return qs.none()

        return qs.none()

    def get_actions(self, request):
        """Only show export actions to users who can view logs."""
        actions = super().get_actions(request)
        if not self.has_module_permission(request):
            return {}
        return actions

    def get_urls(self):
        from django.urls import path as _path
        urls = super().get_urls()
        custom = [
            _path(
                'archive-old-logs/',
                self.admin_site.admin_view(self.archive_old_logs_view),
                name='core_auditlog_archive_old_logs',
            ),
        ]
        return custom + urls

    def archive_old_logs_view(self, request):
        """Handle the 'Archive Old Logs' button POST from the changelist."""
        from django.contrib import messages
        from django.shortcuts import redirect
        from core.utils.audit import AuditLogService
        from core.models.audit import ADMIN_ACTION

        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can trigger log archival.')
            return redirect('admin:core_auditlog_changelist')

        if request.method != 'POST':
            messages.warning(request, 'Invalid request method.')
            return redirect('admin:core_auditlog_changelist')

        days = int(request.POST.get('days', 90))
        days = max(30, min(days, 3650))  # clamp: 30 days – 10 years

        try:
            from core.tasks import archive_old_audit_logs
            result = archive_old_audit_logs.delay(days=days, batch_size=2000)
            AuditLogService.log(
                action=ADMIN_ACTION,
                user=request.user,
                request=request,
                resource_type='AuditLog',
                description=f'Manual archive queued for logs older than {days} days (task {result.id})',
            )
            messages.success(
                request,
                f'Archival task queued (task id: {result.id}). '
                f'Logs older than {days} days will be moved to the archive table in the background.',
            )
        except Exception:
            # Celery not available — run synchronously in a thread to avoid HTTP timeout
            import threading
            from core.management.commands.archive_old_logs import Command

            def _run():
                cmd = Command()
                cmd.stdout = type('_W', (), {'write': lambda self, m: None})()
                cmd.style = type('_S', (), {
                    'SUCCESS': lambda self, m: m,
                    'WARNING': lambda self, m: m,
                })()
                cmd.handle(days=days, batch_size=2000, dry_run=False)

            threading.Thread(target=_run, daemon=True).start()
            AuditLogService.log(
                action=ADMIN_ACTION,
                user=request.user,
                request=request,
                resource_type='AuditLog',
                description=f'Manual archive started synchronously for logs older than {days} days',
            )
            messages.success(
                request,
                f'Archival started in the background (Celery not available). '
                f'Logs older than {days} days are being moved to the archive table.',
            )

        return redirect('admin:core_auditlog_changelist')

    def changelist_view(self, request, extra_context=None):
        """Log that the audit log was viewed; inject archive URL into context."""
        from django.urls import reverse as _rev
        from core.models.audit import AUDIT_LOG_VIEWED
        from core.utils.audit import AuditLogService
        AuditLogService.log(
            action=AUDIT_LOG_VIEWED,
            user=request.user,
            request=request,
            resource_type='AuditLog',
            description=f'{request.user.username} viewed audit log list',
        )
        extra_context = extra_context or {}
        if request.user.is_superuser:
            extra_context['archive_url'] = _rev('admin:core_auditlog_archive_old_logs')
            extra_context['hot_count'] = AuditLog.objects.count()
            from core.models.audit import AuditLogArchive
            extra_context['archive_count'] = AuditLogArchive.objects.count()
        return super().changelist_view(request, extra_context=extra_context)


# ── Login Audit Log ─────────────────────────────────────────────
@admin.register(LoginAuditLog)
class LoginAuditLogAdmin(admin.ModelAdmin):
    """Read-only, non-deletable audit trail for login attempts."""
    list_display = ('timestamp', 'username_attempted', 'success', 'ip_address', 'user_agent_short')
    list_filter = ('success',)
    search_fields = ('username_attempted', 'ip_address')
    readonly_fields = (
        'id', 'user', 'username_attempted', 'ip_address',
        'user_agent', 'timestamp', 'success',
    )
    list_per_page = 50

    def user_agent_short(self, obj):
        """Truncate user-agent for list display."""
        ua = obj.user_agent or ''
        return (ua[:80] + '…') if len(ua) > 80 else ua
    user_agent_short.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLogArchive)
class AuditLogArchiveAdmin(admin.ModelAdmin):
    """Read-only viewer for archived audit logs."""
    list_display = ('timestamp', 'username', 'user_role', 'action',
                    'resource_type', 'resource_label', 'status')
    list_filter = ('action', 'user_role', 'resource_type', 'status')
    search_fields = ('username', 'resource_label', 'resource_id')
    readonly_fields = [f.name for f in AuditLogArchive._meta.get_fields()
                       if hasattr(f, 'column')]
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        user = request.user
        if not user.is_authenticated:
            return False
        return user.is_superuser or getattr(user, 'role', '') == 'admin'


# ── Custom Admin Sidebar Grouping ────────────────────────────────
_ADMIN_GROUPS = [
    {
        'name': 'Users & Access',
        'models': ['Examiner', 'UserSession', 'Group'],
    },
    {
        'name': 'Logs & Audit',
        'models': ['AuditLog', 'AuditLogArchive', 'LoginAuditLog', 'AccessAttempt', 'AccessFailureLog', 'AccessLog'],
    },
    {
        'name': 'Courses & Curriculum',
        'models': ['Theme', 'Course', 'ILO'],
    },
    {
        'name': 'Exam Management',
        'models': ['Exam', 'Station', 'ChecklistItem', 'Path',
                   'ExamSession', 'SessionStudent', 'ExaminerAssignment',
                   'StationScore', 'ItemScore'],
    },
    {
        'name': 'OSCE Paths',
        'models': ['OSCEExamPath', 'OSCERoomAssignment', 'OSCEPathStudent'],
    },
    {
        'name': 'Library & Templates',
        'models': ['ChecklistLibrary', 'StationVariant',
                   'TemplateLibrary', 'StationTemplate'],
    },
]

_original_get_app_list = admin.AdminSite.get_app_list


def _custom_get_app_list(self, request, app_label=None):
    """Reorganise the admin sidebar into logical groups."""
    original = _original_get_app_list(self, request, app_label)

    # When filtering by a single app (e.g. breadcrumb links), use the
    # default behaviour so individual app pages still work correctly.
    if app_label is not None:
        return original

    # Build a flat lookup: object_name -> model dict
    model_lookup: dict = {}
    for app in original:
        for model in app['models']:
            model_lookup[model['object_name']] = model

    custom_list = []
    used: set = set()

    for group in _ADMIN_GROUPS:
        models = []
        for name in group['models']:
            if name in model_lookup:
                models.append(model_lookup[name])
                used.add(name)
        if models:
            custom_list.append({
                'name': group['name'],
                'app_label': group['name'],
                'app_url': '#',
                'has_module_perms': True,
                'models': models,
            })

    # Catch-all for any registered model not in the explicit groups
    remaining = [m for app in original for m in app['models']
                 if m['object_name'] not in used]
    if remaining:
        custom_list.append({
            'name': 'Other',
            'app_label': 'other',
            'app_url': '#',
            'has_module_perms': True,
            'models': remaining,
        })

    return custom_list


admin.AdminSite.get_app_list = _custom_get_app_list

# ── Department ────────────────────────────────────────────────────
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'created_at')
    search_fields = ('name',)

# ── Rename Examiner in admin sidebar to "Users Profiles" ─────────
# We patch _meta here (admin-only) so no migration is needed.
Examiner._meta.verbose_name = 'Users Profile'
Examiner._meta.verbose_name_plural = 'Users Profiles'

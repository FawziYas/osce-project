"""
Django admin registration for all core models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
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
    DryQuestion, MCQOption, DryStationResponse,
    OSCEExamPath, OSCERoomAssignment, OSCEPathStudent,
    StationVariant, TemplateLibrary, StationTemplate, AuditLog,
    LoginAuditLog, UserSession, UserProfile,
)


# ── User Profiles (default-password / forced-change tracking) ────
@admin.action(description='Reset selected users to default password')
def reset_to_default_password(modeladmin, request, queryset):
    """Set password back to DEFAULT_USER_PASSWORD and flag must_change_password."""
    from django.conf import settings as _settings

    if not request.user.is_superuser:
        modeladmin.message_user(request, 'Only superusers can reset passwords.', level='ERROR')
        return

    default_pw = getattr(_settings, 'DEFAULT_USER_PASSWORD', '123456789')
    count = 0
    for profile in queryset.select_related('user'):
        profile.user.set_password(default_pw)
        profile.user.save(update_fields=['password'])
        profile.must_change_password = True
        profile.password_changed_at = None
        profile.save(update_fields=['must_change_password', 'password_changed_at'])
        audit_logger.warning(
            "Admin '%s' reset password for user '%s'.",
            request.user.username, profile.user.username,
        )
        count += 1
    modeladmin.message_user(request, f'{count} user(s) reset to default password.')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'get_email', 'must_change_password', 'password_changed_at')
    list_filter = ('must_change_password',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'password_changed_at')
    actions = [reset_to_default_password]
    ordering = ('user__username',)

    @admin.display(description='Username', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username

    @admin.display(description='Email', ordering='user__email')
    def get_email(self, obj):
        return obj.user.email

    def has_add_permission(self, request):
        return False  # Profiles are created automatically by the signal

    def has_delete_permission(self, request, obj=None):
        return False  # Never delete profiles manually


# ── Active User Sessions ─────────────────────────────────────────
@admin.action(description='End selected sessions')
def end_sessions(modeladmin, request, queryset):
    """Delete Django session records and UserSession rows for selected entries."""
    from django.contrib.sessions.models import Session
    keys = list(queryset.values_list('session_key', flat=True))
    Session.objects.filter(session_key__in=keys).delete()
    queryset.delete()
    audit_logger.warning(
        'ADMIN: ended %d session(s) for [%s] by %s',
        len(keys), ', '.join(keys), request.user.username
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'created_at', 'session_status')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'session_key')
    readonly_fields = ('user', 'session_key', 'created_at')
    actions = [end_sessions]
    ordering = ('-created_at',)

    @admin.display(description='Session alive?')
    def session_status(self, obj):
        return '✅ Active' if obj.is_session_alive() else '❌ Expired'

    def has_add_permission(self, request):
        return False  # Sessions are created by the login flow only

    def delete_model(self, request, obj):
        """Ensure Django Session row is also purged."""
        from django.contrib.sessions.models import Session
        Session.objects.filter(session_key=obj.session_key).delete()
        super().delete_model(request, obj)


# ── Custom User Admin ─────────────────────────────────────────────
@admin.register(Examiner)
class ExaminerAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'full_name', 'role', 'title', 'department', 'is_active', 'is_deleted', 'is_staff')
    list_filter = ('role', 'is_active', 'is_deleted', 'is_staff', 'department')
    search_fields = ('username', 'email', 'full_name')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'title', 'department')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )

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
    fields = ('number', 'description', 'osce_marks', 'theme', 'active')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'short_code', 'name', 'year_level', 'active')
    list_filter = ('year_level', 'active')
    search_fields = ('code', 'short_code', 'name')
    inlines = [ILOInline]


@admin.register(ILO)
class ILOAdmin(admin.ModelAdmin):
    list_display = ('number', 'course', 'theme', 'osce_marks', 'active')
    list_filter = ('course', 'theme', 'active')


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
    fields = ('item_number', 'description', 'points', 'is_critical', 'rubric_type')


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('station_number', 'name', 'path', 'duration_minutes', 'active')
    list_filter = ('active', 'is_deleted')
    search_fields = ('name',)
    inlines = [ChecklistItemInline]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('item_number', 'description', 'station', 'points', 'is_critical')


def _get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def revert_to_scheduled(modeladmin, request, queryset):
    """Admin action: revert completed sessions back to scheduled."""
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
        if previous_status != 'completed':
            skipped += 1
            modeladmin.message_user(
                request,
                f'Skipped "{session.name}" – status is "{previous_status}", not "completed".',
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
    list_display = ('examiner', 'station', 'session', 'is_primary')
    list_filter = ('is_primary',)


# ── Library ──────────────────────────────────────────────────────
@admin.register(ChecklistLibrary)
class ChecklistLibraryAdmin(admin.ModelAdmin):
    list_display = ('id', 'ilo', 'description', 'suggested_points', 'usage_count', 'active')
    list_filter = ('active',)


# ── Dry Stations ────────────────────────────────────────────────
@admin.register(DryQuestion)
class DryQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_number', 'station', 'question_type', 'points')
    list_filter = ('question_type',)


@admin.register(MCQOption)
class MCQOptionAdmin(admin.ModelAdmin):
    list_display = ('question', 'option_number', 'option_text', 'is_correct')


@admin.register(DryStationResponse)
class DryStationResponseAdmin(admin.ModelAdmin):
    list_display = ('question', 'student', 'final_score', 'submitted_at')


# ── OSCE Paths ──────────────────────────────────────────────────
@admin.register(OSCEExamPath)
class OSCEExamPathAdmin(admin.ModelAdmin):
    list_display = ('path_number', 'exam_session', 'start_time', 'status')


@admin.register(OSCERoomAssignment)
class OSCERoomAssignmentAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_name', 'station', 'examiner_name', 'status')


@admin.register(OSCEPathStudent)
class OSCEPathStudentAdmin(admin.ModelAdmin):
    list_display = ('osce_path', 'room_assignment', 'student')


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
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'username', 'action', 'resource_type', 'resource_id', 'ip_address')
    list_filter = ('action', 'resource_type')
    search_fields = ('username', 'description', 'resource_id')
    readonly_fields = ('id', 'user', 'username', 'action', 'resource_type', 'resource_id',
                       'description', 'ip_address', 'user_agent', 'extra_data', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ── Login Audit Log ─────────────────────────────────────────────
@admin.register(LoginAuditLog)
class LoginAuditLogAdmin(admin.ModelAdmin):
    """Read-only, non-deletable audit trail for login attempts."""
    list_display = ('timestamp', 'username_attempted', 'success', 'ip_address', 'user_agent_short')
    list_filter = ('success', 'timestamp')
    search_fields = ('username_attempted', 'ip_address')
    readonly_fields = (
        'id', 'user', 'username_attempted', 'ip_address',
        'user_agent', 'timestamp', 'success',
    )
    date_hierarchy = 'timestamp'
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

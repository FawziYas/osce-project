"""
Course and ILO CRUD views.
"""
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponseForbidden

from core.models import Course, ILO, Theme
from core.models.department import Department
from core.utils.sanitize import strip_html
from core.utils.roles import (
    scope_queryset, check_course_department, is_global, is_coordinator,
    get_user_department, is_head_coordinator, admin_or_superuser_required,
    head_or_admin_required,
)


# =============================================================================
# COURSE MANAGEMENT
# =============================================================================

@login_required
def course_list(request):
    """List courses — scoped to user's department for coordinators."""
    user = request.user
    dept = getattr(user, 'department', None)
    cache_key = f'course_list_{user.pk}_{dept.pk if dept else "all"}'
    courses = cache.get(cache_key)
    if courses is None:
        courses = list(
            scope_queryset(user, Course.objects.all(), dept_field='department')
            .order_by('year_level', 'code')
        )
        cache.set(cache_key, courses, timeout=1800)  # 30 min
    can_add_course = user.is_superuser or getattr(user, 'role', None) == 'admin'
    can_edit_course = can_add_course or is_head_coordinator(user)
    return render(request, 'creator/courses/list.html', {
        'courses': courses,
        'can_add_course': can_add_course,
        'can_edit_course': can_edit_course,
    })


@login_required
@admin_or_superuser_required
def course_create(request):
    """Create a new course — admin and superuser only."""
    user = request.user
    user_dept = get_user_department(user)

    # Coordinators only see their department; globals see all
    if user_dept:
        departments = Department.objects.filter(pk=user_dept.pk)
    else:
        departments = Department.objects.order_by('name')

    if request.method == 'POST':
        osce_mark_raw = request.POST.get('osce_mark', '').strip()
        dept_id = request.POST.get('department', '').strip()

        # Coordinator can only create in their own department
        if is_coordinator(user) and user_dept and dept_id and str(dept_id) != str(user_dept.pk):
            return HttpResponseForbidden('You can only create courses in your own department.')

        course = Course.objects.create(
            code=request.POST['code'],
            short_code=request.POST['short_code'],
            name=strip_html(request.POST['name']),
            year_level=int(request.POST.get('year_level', 1)),
            description=strip_html(request.POST.get('description', '')),
            osce_mark=int(osce_mark_raw) if osce_mark_raw else None,
            department_id=int(dept_id) if dept_id else None,
        )
        messages.success(request, f'Course "{course.code}" created successfully.')
        next_url = request.POST.get('next')
        if next_url:
            from django.utils.http import url_has_allowed_host_and_scheme
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
        return redirect('creator:course_detail', course_id=course.id)

    return render(request, 'creator/courses/form.html', {'course': None, 'year_range': range(1, 7), 'departments': departments})


@login_required
def course_detail(request, course_id):
    """View course details and ILOs — dept-scoped."""
    course = get_object_or_404(Course, pk=course_id)
    if not check_course_department(request.user, course):
        return HttpResponseForbidden('You do not have access to this course.')
    ilos = ILO.objects.filter(course_id=course_id).order_by('number')
    user = request.user
    can_add_course = user.is_superuser or getattr(user, 'role', None) == 'admin'
    can_edit_course = can_add_course or is_head_coordinator(user)
    return render(request, 'creator/courses/detail.html', {
        'course': course,
        'ilos': ilos,
        'can_add_course': can_add_course,
        'can_edit_course': can_edit_course,
    })


@login_required
@head_or_admin_required
def course_edit(request, course_id):
    """Edit a course — head coordinator, admin and superuser only."""
    course = get_object_or_404(Course, pk=course_id)
    if not check_course_department(request.user, course):
        return HttpResponseForbidden('You do not have access to this course.')

    user_dept = get_user_department(request.user)
    if user_dept:
        departments = Department.objects.filter(pk=user_dept.pk)
    else:
        departments = Department.objects.order_by('name')

    if request.method == 'POST':
        course.code = request.POST['code']
        course.short_code = request.POST['short_code']
        course.name = strip_html(request.POST['name'])
        course.year_level = int(request.POST.get('year_level', course.year_level))
        course.description = strip_html(request.POST.get('description', ''))
        osce_mark_raw = request.POST.get('osce_mark', '').strip()
        course.osce_mark = int(osce_mark_raw) if osce_mark_raw else None
        dept_id = request.POST.get('department', '').strip()
        course.department_id = int(dept_id) if dept_id else None
        course.save()
        messages.success(request, f'Course "{course.code}" updated.')
        next_url = request.POST.get('next')
        if next_url:
            from django.utils.http import url_has_allowed_host_and_scheme
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
        return redirect('creator:course_detail', course_id=course.id)

    return render(request, 'creator/courses/form.html', {'course': course, 'year_range': range(1, 7), 'departments': departments})


# =============================================================================
# ILO MANAGEMENT
# =============================================================================

@login_required
@head_or_admin_required
def ilo_create(request, course_id):
    """Create a new ILO for a course — head coordinator, admin and superuser only."""
    course = get_object_or_404(Course, pk=course_id)
    if not check_course_department(request.user, course):
        return HttpResponseForbidden('You do not have access to this course.')

    if request.method == 'POST':
        max_num = ILO.objects.filter(course_id=course_id).aggregate(
            m=Max('number')
        )['m'] or 0

        ILO.objects.create(
            course_id=course_id,
            number=max_num + 1,
            description=strip_html(request.POST['description']),
            theme_id=int(request.POST.get('theme_id', 1)) if request.POST.get('theme_id') else None,
            osce_marks=int(request.POST.get('osce_marks', 0)),
        )
        messages.success(request, f'ILO {max_num + 1} created.')
        return redirect('creator:course_detail', course_id=course_id)

    themes = Theme.objects.filter(active=True).order_by('display_order')
    return render(request, 'creator/ilos/form.html', {
        'course': course,
        'ilo': None,
        'themes': themes,
    })


@login_required
@head_or_admin_required
def ilo_edit(request, ilo_id):
    """Edit an ILO — head coordinator, admin and superuser only."""
    ilo = get_object_or_404(ILO, pk=ilo_id)
    if not check_course_department(request.user, ilo.course):
        return HttpResponseForbidden('You do not have access to this ILO.')

    if request.method == 'POST':
        ilo.description = strip_html(request.POST['description'])
        ilo.theme_id = int(request.POST.get('theme_id')) if request.POST.get('theme_id') else None
        ilo.osce_marks = int(request.POST.get('osce_marks', 0))
        ilo.save()
        messages.success(request, f'ILO {ilo.number} updated.')
        return redirect('creator:course_detail', course_id=ilo.course_id)

    themes = Theme.objects.filter(active=True).order_by('display_order')
    return render(request, 'creator/ilos/form.html', {
        'course': ilo.course,
        'ilo': ilo,
        'themes': themes,
    })

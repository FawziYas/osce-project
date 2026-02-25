"""
Course and ILO CRUD views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max

from core.models import Course, ILO, Theme


# =============================================================================
# COURSE MANAGEMENT
# =============================================================================

@login_required
def course_list(request):
    """List all courses."""
    courses = Course.objects.order_by('year_level', 'code').all()
    return render(request, 'creator/courses/list.html', {'courses': courses})


@login_required
def course_create(request):
    """Create a new course."""
    if request.method == 'POST':
        osce_mark_raw = request.POST.get('osce_mark', '').strip()
        course = Course.objects.create(
            code=request.POST['code'],
            name=request.POST['name'],
            year_level=int(request.POST.get('year_level', 1)),
            description=request.POST.get('description', ''),
            osce_mark=int(osce_mark_raw) if osce_mark_raw else None,
        )
        messages.success(request, f'Course "{course.code}" created successfully.')
        return redirect('creator:course_detail', course_id=course.id)

    return render(request, 'creator/courses/form.html', {'course': None, 'year_range': range(1, 7)})


@login_required
def course_detail(request, course_id):
    """View course details and ILOs."""
    course = get_object_or_404(Course, pk=course_id)
    ilos = ILO.objects.filter(course_id=course_id).order_by('number')
    return render(request, 'creator/courses/detail.html', {
        'course': course,
        'ilos': ilos,
    })


@login_required
def course_edit(request, course_id):
    """Edit a course."""
    course = get_object_or_404(Course, pk=course_id)

    if request.method == 'POST':
        course.code = request.POST['code']
        course.name = request.POST['name']
        course.year_level = int(request.POST.get('year_level', course.year_level))
        course.description = request.POST.get('description', '')
        osce_mark_raw = request.POST.get('osce_mark', '').strip()
        course.osce_mark = int(osce_mark_raw) if osce_mark_raw else None
        course.save()
        messages.success(request, f'Course "{course.code}" updated.')
        return redirect('creator:course_detail', course_id=course.id)

    return render(request, 'creator/courses/form.html', {'course': course, 'year_range': range(1, 7)})


# =============================================================================
# ILO MANAGEMENT
# =============================================================================

@login_required
def ilo_create(request, course_id):
    """Create a new ILO for a course."""
    course = get_object_or_404(Course, pk=course_id)

    if request.method == 'POST':
        max_num = ILO.objects.filter(course_id=course_id).aggregate(
            m=Max('number')
        )['m'] or 0

        ILO.objects.create(
            course_id=course_id,
            number=max_num + 1,
            description=request.POST['description'],
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
def ilo_edit(request, ilo_id):
    """Edit an ILO."""
    ilo = get_object_or_404(ILO, pk=ilo_id)

    if request.method == 'POST':
        ilo.description = request.POST['description']
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

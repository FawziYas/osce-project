"""
Creator API – Course & ILO endpoints.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Course, ILO, ChecklistLibrary
from core.utils.roles import scope_queryset


@login_required
@require_GET
def get_courses(request):
    """GET /api/creator/courses"""
    # P4: Use annotate to eliminate N+1 count per course
    courses = scope_queryset(
        request.user,
        Course.objects.annotate(_ilo_count=Count('ilos')),
        dept_field='department',
    ).order_by('code')
    return JsonResponse([{
        'id': c.id,
        'code': c.code,
        'name': c.name,
        'year_level': c.year_level,
        'osce_mark': c.osce_mark,
        'ilo_count': c._ilo_count,
    } for c in courses], safe=False)


@login_required
@require_GET
def get_course_ilos(request, course_id):
    """GET /api/creator/courses/<id>/ilos"""
    # Verify user can access this course's department
    course = get_object_or_404(
        scope_queryset(request.user, Course.objects.all(), dept_field='department'),
        pk=course_id,
    )
    # P4: Use annotate to eliminate N+1 count per ILO
    ilos = ILO.objects.filter(
        course_id=course_id
    ).select_related('theme').annotate(
        _library_count=Count('library_items'),
    ).order_by('number')

    return JsonResponse([{
        'id': ilo.id,
        'number': ilo.number,
        'description': ilo.description,
        'theme_id': ilo.theme_id,
        'theme_name': ilo.theme_name,
        'theme_color': ilo.theme_color,
        'theme_icon': ilo.theme_icon,
        'osce_marks': ilo.osce_marks,
        'library_count': ilo._library_count,
    } for ilo in ilos], safe=False)


@login_required
@require_GET
def get_ilo_library(request, ilo_id):
    """GET /api/creator/ilos/<id>/library"""
    # Verify user can access this ILO's department via its course
    ilo = get_object_or_404(
        scope_queryset(request.user, ILO.objects.all(), dept_field='course__department'),
        pk=ilo_id,
    )
    items = ChecklistLibrary.objects.filter(ilo_id=ilo_id).order_by('id')
    return JsonResponse([{
        'id': item.id,
        'description': item.description,
        'expected_response': item.expected_response,
        'points': item.suggested_points,
        'usage_count': item.usage_count or 0,
    } for item in items], safe=False)

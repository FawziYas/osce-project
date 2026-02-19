"""
Creator API – Course & ILO endpoints.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Course, ILO, ChecklistLibrary


@login_required
@require_GET
def get_courses(request):
    """GET /api/creator/courses"""
    courses = Course.objects.filter(active=True).order_by('code')
    return JsonResponse([{
        'id': c.id,
        'code': c.code,
        'name': c.name,
        'year_level': c.year_level,
        'ilo_count': c.ilos.filter(active=True).count(),
    } for c in courses], safe=False)


@login_required
@require_GET
def get_course_ilos(request, course_id):
    """GET /api/creator/courses/<id>/ilos"""
    ilos = ILO.objects.filter(
        course_id=course_id, active=True
    ).select_related('theme').order_by('number')

    return JsonResponse([{
        'id': ilo.id,
        'number': ilo.number,
        'description': ilo.description,
        'theme_id': ilo.theme_id,
        'theme_name': ilo.theme_name,
        'theme_color': ilo.theme_color,
        'theme_icon': ilo.theme_icon,
        'osce_marks': ilo.osce_marks,
        'library_count': ilo.library_items.count(),
    } for ilo in ilos], safe=False)


@login_required
@require_GET
def get_ilo_library(request, ilo_id):
    """GET /api/creator/ilos/<id>/library"""
    items = ChecklistLibrary.objects.filter(ilo_id=ilo_id).order_by('id')
    return JsonResponse([{
        'id': item.id,
        'description': item.description,
        'is_critical': item.is_critical,
        'interaction_type': item.interaction_type,
        'expected_response': item.expected_response,
        'points': item.suggested_points,
        'usage_count': item.usage_count or 0,
    } for item in items], safe=False)

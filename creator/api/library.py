"""
Creator API – Library endpoints.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from core.models import ILO, ChecklistLibrary


@login_required
@require_GET
def get_library(request):
    """GET /api/creator/library – grouped by ILO."""
    items = ChecklistLibrary.objects.select_related(
        'ilo', 'ilo__course', 'ilo__theme'
    ).order_by('ilo__course_id', 'ilo__number')

    grouped = {}
    for item in items:
        ilo = item.ilo
        if ilo.id not in grouped:
            grouped[ilo.id] = {
                'ilo_id': ilo.id,
                'ilo_number': ilo.number,
                'ilo_description': ilo.description,
                'course_code': ilo.course.code if ilo.course else None,
                'theme_id': ilo.theme_id,
                'theme_name': ilo.theme.name if ilo.theme else 'Unknown',
                'theme_color': ilo.theme.color if ilo.theme else '#6c757d',
                'items': [],
            }
        grouped[ilo.id]['items'].append({
            'id': item.id,
            'description': item.description,
            'is_critical': item.is_critical,
            'interaction_type': item.interaction_type,
            'suggested_points': item.suggested_points,
            'usage_count': item.usage_count or 0,
        })

    return JsonResponse(list(grouped.values()), safe=False)


@login_required
@require_POST
def create_library_item(request):
    """POST /api/creator/library"""
    data = json.loads(request.body)
    if not data.get('ilo_id') or not data.get('description'):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    item = ChecklistLibrary.objects.create(
        ilo_id=data['ilo_id'],
        description=data['description'],
        is_critical=data.get('is_critical', False),
        interaction_type=data.get('interaction_type', 'passive'),
        expected_response=data.get('expected_response', ''),
        suggested_points=data.get('suggested_points', 1),
        usage_count=0,
    )
    return JsonResponse({
        'id': item.id,
        'description': item.description,
        'message': 'Library item created',
    }, status=201)


@login_required
def delete_library_item(request, item_id):
    """DELETE /api/creator/library/<id>"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    item = get_object_or_404(ChecklistLibrary, pk=item_id)
    if item.usage_count and item.usage_count > 0:
        return JsonResponse(
            {'error': f'Cannot delete: item used in {item.usage_count} station(s)'},
            status=400,
        )

    item.delete()
    return JsonResponse({'message': 'Library item deleted'})

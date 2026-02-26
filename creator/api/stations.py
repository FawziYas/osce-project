"""
Creator API – Station delete/restore endpoints.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.models import Station, StationScore


@login_required
def delete_station_api(request, station_id):
    """DELETE /api/creator/stations/<id>"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    station = get_object_or_404(Station, pk=station_id)

    score_count = StationScore.objects.filter(station=station).count()
    if score_count > 0:
        return JsonResponse(
            {'error': f'Cannot delete: {score_count} student scores exist for this station'},
            status=400,
        )

    name = station.name
    station.delete()
    return JsonResponse({'message': f"Station '{name}' deleted"})




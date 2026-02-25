"""
Checklist Library views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from core.models import Course, ILO, ChecklistLibrary


@login_required
def library_list(request):
    """List all library items grouped by course/ILO."""
    courses = Course.objects.order_by('short_code', 'code')
    ilos = ILO.objects.select_related(
        'course', 'theme'
    ).order_by('course__code', 'number')
    total_items = ChecklistLibrary.objects.count()

    return render(request, 'creator/library/list.html', {
        'ilos': ilos,
        'courses': courses,
        'total_items': total_items,
    })


@login_required
def library_item_create(request):
    """Create a new library item."""
    courses = Course.objects.order_by('code')

    if request.method == 'POST':
        ChecklistLibrary.objects.create(
            ilo_id=int(request.POST['ilo_id']),
            description=request.POST['description'],
            is_critical=request.POST.get('is_critical') == 'on',
            interaction_type=request.POST.get('interaction_type', 'passive'),
            expected_response=request.POST.get('expected_response', ''),
            suggested_points=float(request.POST.get('points', 1)),
            usage_count=0,
        )
        messages.success(request, 'Library item created.')
        return redirect('creator:library_list')

    return render(request, 'creator/library/form.html', {'item': None, 'courses': courses})


@login_required
def library_item_edit(request, item_id):
    """Edit a library item."""
    item = get_object_or_404(ChecklistLibrary, pk=item_id)
    courses = Course.objects.order_by('code')

    if request.method == 'POST':
        item.ilo_id = int(request.POST['ilo_id'])
        item.description = request.POST['description']
        item.is_critical = request.POST.get('is_critical') == 'on'
        item.interaction_type = request.POST.get('interaction_type', 'passive')
        item.expected_response = request.POST.get('expected_response', '')
        item.suggested_points = float(request.POST.get('points', 1))
        item.save()
        messages.success(request, 'Library item updated.')
        return redirect('creator:library_list')

    return render(request, 'creator/library/form.html', {'item': item, 'courses': courses})

"""Examiner API URLs."""
from django.urls import path
from .views import api

app_name = 'examiner_api'

urlpatterns = [
    path('session/<uuid:session_id>/students/', api.get_session_students, name='session_students'),
    path('station/<uuid:station_id>/checklist/', api.get_station_checklist, name='station_checklist'),
    path('score/start/', api.start_marking, name='start_marking'),
    path('score/<uuid:station_score_id>/item/', api.mark_item, name='mark_item'),
    path('score/<uuid:station_score_id>/submit/', api.submit_score, name='submit_score'),
    path('score/<uuid:station_score_id>/undo/', api.undo_submit, name='undo_submit'),
    path('sync/', api.sync_offline_data, name='sync'),
    path('sync/status/', api.sync_status, name='sync_status'),
]

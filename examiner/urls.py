"""Examiner page URLs."""
from django.urls import path
from .views import pages

app_name = 'examiner'

urlpatterns = [
    path('', pages.index, name='index'),
    path('offline/', pages.offline, name='offline'),
    path('login/', pages.login_view, name='login'),
    path('logout/', pages.logout_view, name='logout'),
    path('home/', pages.home, name='home'),
    path('all-sessions/', pages.all_sessions, name='all_sessions'),
    path('station/<uuid:assignment_id>/', pages.station_dashboard, name='station_dashboard'),
    path('station/<uuid:assignment_id>/select-student/', pages.select_student, name='select_student'),
    path('mark/<uuid:assignment_id>/<uuid:student_id>/', pages.marking_interface, name='marking_interface'),
]

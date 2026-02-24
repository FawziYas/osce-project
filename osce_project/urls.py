"""
Root URL configuration for OSCE Django project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from core.views import login_view, logout_view, admin_gateway_view, force_change_password_view, profile_view

urlpatterns = [
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('change-password/', force_change_password_view, name='force_change_password'),
    path('profile/', profile_view, name='profile'),
    # Admin gateway MUST be before the admin include — otherwise the admin
    # include swallows manage-osce-exam-77x/gateway/ and returns catch_all 404.
    path(f"{settings.SECRET_ADMIN_URL}/gateway/", admin_gateway_view, name='admin_gateway'),
    # Secret admin URL — path driven entirely by SECRET_ADMIN_URL in .env
    path(f"{settings.SECRET_ADMIN_URL}/", admin.site.urls),
    path('examiner/', include('examiner.urls')),
    path('creator/', include('creator.urls')),
    # API routes (examiner at /api/ to match JS fetch paths)
    path('api/', include('examiner.api_urls')),
    path('api/creator/', include('creator.api_urls')),
]

# Custom error handlers
handler404 = 'core.error_handlers.handler404'
handler500 = 'core.error_handlers.handler500'
handler403 = 'core.error_handlers.handler403'
handler400 = 'core.error_handlers.handler400'


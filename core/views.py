"""
Core views – unified authentication for all user types.
"""
from axes.decorators import axes_dispatch
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import redirect, render

from core.utils.audit import log_action


def _redirect_by_role(user):
    """Redirect user to the correct interface based on their role hierarchy."""
    if user.is_superuser or getattr(user, 'role', None) in ('admin', 'coordinator'):
        return redirect('/creator/')
    return redirect('/examiner/home/')


@axes_dispatch
def login_view(request):
    """Unified login – redirects to examiner or creator interface based on role."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
            return render(request, 'login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            log_action(request, 'LOGIN', 'User', user.id,
                       f'{user.display_name} logged in (role: {getattr(user, "role", "superuser")})')
            return _redirect_by_role(user)

        messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


def logout_view(request):
    """Unified logout – clears session and redirects to /login/."""
    if request.user.is_authenticated:
        log_action(request, 'LOGOUT', 'User', request.user.id,
                   f'{request.user.display_name} logged out')
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('/login/')

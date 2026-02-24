"""
Core views – unified authentication for all user types.
"""
import logging

from axes.decorators import axes_dispatch
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import Http404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.conf import settings

from core.forms import ForcePasswordChangeForm, UserPasswordChangeForm
from core.utils.audit import log_action
from core.models.user_session import UserSession

logger = logging.getLogger(__name__)
auth_logger = logging.getLogger('osce.auth')


def _get_client_ip(request):
    """Extract real client IP, honouring X-Forwarded-For for proxied setups."""
    trusted = getattr(settings, 'TRUSTED_PROXIES', [])
    remote = request.META.get('REMOTE_ADDR', '')
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded and (not trusted or remote in trusted):
        return forwarded.split(',')[0].strip()
    return remote or None


def _redirect_by_role(user):
    """Redirect user to the correct interface based on their role hierarchy."""
    if user.is_superuser or getattr(user, 'role', None) in ('admin', 'coordinator'):
        return redirect('/creator/')
    return redirect('/examiner/home/')


@axes_dispatch
@never_cache
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
            ip = _get_client_ip(request)

            # ── Single-active-session check ───────────────────────────────
            try:
                existing = UserSession.objects.get(user=user)
                if existing.is_session_alive():
                    # A real open session exists — block this login
                    logger.warning(
                        "Blocked login for user '%s' from IP %s — "
                        "active session already exists.",
                        user.username, ip
                    )
                    messages.error(
                        request,
                        'There is already an open session for this account. '
                        'If your computer crashed, ask the Administrator to '
                        'end your previous session.'
                    )
                    return render(request, 'login.html')
                else:
                    # Stale record (session expired/deleted) — clean it up
                    existing.delete()
            except UserSession.DoesNotExist:
                pass  # No prior session — proceed normally
            # ─────────────────────────────────────────────────────────────

            login(request, user)

            # Record the new active session
            UserSession.objects.update_or_create(
                user=user,
                defaults={'session_key': request.session.session_key}
            )

            logger.info(
                "User '%s' logged in successfully from IP %s. Session key: %s.",
                user.username, ip, request.session.session_key
            )
            log_action(request, 'LOGIN', 'User', user.id,
                       f'{user.display_name} logged in (role: {getattr(user, "role", "superuser")})')
            return _redirect_by_role(user)

        messages.error(request, 'Invalid username or password. (Username is case-sensitive)')

    return render(request, 'login.html')


def logout_view(request):
    """Unified logout – clears session and redirects to /login/."""
    if request.user.is_authenticated:
        log_action(request, 'LOGOUT', 'User', request.user.id,
                   f'{request.user.display_name} logged out')
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('/login/')


@require_POST
def admin_gateway_view(request):
    """
    Admin gateway: validates a secret token from POST, then sets a session flag
    that unlocks the secret admin URL for this session.

    Security model:
    - The gateway URL itself is also secret (served under SECRET_ADMIN_URL path).
    - Correct token  → sets session['admin_unlocked'] = True, redirects to admin.
    - Wrong token    → raises Http404 (no information leak).
    - Only superusers and admins can reach admin after unlock.
    - Uses reverse('admin:index') — never hardcodes the admin path.
    """
    token = request.POST.get('token', '')
    expected = settings.SECRET_ADMIN_URL  # reuse the URL secret as access token

    if not request.user.is_authenticated:
        raise Http404

    if not request.user.is_staff:
        raise Http404

    if token != expected:
        raise Http404

    # Set the session gate and redirect through reverse() — no hardcoded path
    request.session['admin_unlocked'] = True
    log_action(request, 'ADMIN_ACCESS', 'User', request.user.id,
               f'{request.user.display_name} unlocked admin panel')
    return redirect(reverse('admin:index'))


# ── Forced password change ────────────────────────────────────────────
@login_required
def force_change_password_view(request):
    """
    Full-screen modal that blocks the user until they set a new password.
    Shown to any user whose profile.must_change_password is True.
    """
    if request.method == 'POST':
        form = ForcePasswordChangeForm(request.POST)
        if form.is_valid():
            user = request.user
            user.set_password(form.cleaned_data['new_password'])
            user.save(update_fields=['password'])

            # Keep the session alive after the password change
            update_session_auth_hash(request, user)

            # Clear the flag
            profile = user.profile
            profile.must_change_password = False
            profile.password_changed_at = timezone.now()
            profile.save(update_fields=['must_change_password', 'password_changed_at'])

            auth_logger.info(
                "User '%s' changed their password from default.", user.username
            )
            log_action(request, 'PASSWORD_CHANGE', 'User', user.id,
                       f'{user.display_name} changed default password')

            messages.success(request, 'Password updated successfully.')
            return _redirect_by_role(user)
    else:
        form = ForcePasswordChangeForm()

    return render(request, 'force_change_password.html', {'form': form})


@login_required
@never_cache
def profile_view(request):
    """User profile page — view account info and change password."""
    user = request.user
    password_form = UserPasswordChangeForm(user=user)

    if request.method == 'POST':
        password_form = UserPasswordChangeForm(user=user, data=request.POST)
        if password_form.is_valid():
            user.set_password(password_form.cleaned_data['new_password'])
            user.save(update_fields=['password'])
            update_session_auth_hash(request, user)
            auth_logger.info(
                "User '%s' successfully changed their password.", user.username
            )
            log_action(request, 'PASSWORD_CHANGE', 'User', user.id,
                       f'{user.display_name} changed their password from profile page')
            messages.success(request, 'Password updated successfully.')
            return redirect('profile')
        else:
            logger.warning(
                "Failed password change for user '%s' from IP %s.",
                user.username, _get_client_ip(request)
            )

    # Choose the right base template based on the user's role
    if user.is_superuser or getattr(user, 'role', None) in ('admin', 'coordinator'):
        base_template = 'creator/base_creator.html'
        home_url = '/creator/'
        is_examiner_view = False
    else:
        base_template = 'examiner/base_examiner.html'
        home_url = '/examiner/home/'
        is_examiner_view = True

    # Convert Unix timestamp to aware datetime for display
    account_created = None
    if user.created_at:
        from datetime import datetime, timezone as dt_timezone
        account_created = datetime.fromtimestamp(user.created_at, tz=dt_timezone.utc)

    return render(request, 'profile.html', {
        'password_form': password_form,
        'base_template': base_template,
        'account_created': account_created,
        'home_url': home_url,
        'is_examiner_view': is_examiner_view,
    })

    return render(request, 'force_change_password.html', {'form': form})

"""
Layer 5 — Session State Guard.

Enforces:
  1. Score creation (POST) only during an ACTIVE session
  2. Score updates (PUT/PATCH) only while the score is NOT finalized
  3. Returns structured error responses with proper codes
"""
from rest_framework.exceptions import PermissionDenied

from core.api.exceptions import SESSION_NOT_ACTIVE, SCORE_FINALIZED


class SessionNotActiveError(PermissionDenied):
    """Raised when an examiner tries to submit a score outside an active session."""
    default_detail = 'Session is not active. Scoring is only allowed during an active exam session.'
    default_code = SESSION_NOT_ACTIVE


class ScoreFinalizedError(PermissionDenied):
    """Raised when attempting to modify a finalized (submitted) score."""
    default_detail = 'This score has been finalized and cannot be modified.'
    default_code = SCORE_FINALIZED


class SessionStateGuard:
    """
    Mixin for score-writing ViewSets.

    Checks:
      - On create(): the station's session must have status='in_progress'
      - On update(): the StationScore must NOT have status='submitted'
                     (unless unlocked_for_correction=True)

    Subclasses must resolve the session from the station being scored.
    """

    def _get_station_session(self, station):
        """Walk Station → Path → ExamSession."""
        if station.path and station.path.session:
            return station.path.session
        return None

    def perform_create(self, serializer):
        """Guard: block score creation if session is not active."""
        station = serializer.validated_data.get('station')
        if station is None:
            # Try to get from the view context (nested route)
            station = getattr(self, '_station', None)

        if station:
            session = self._get_station_session(station)
            if session and session.status != 'in_progress':
                raise SessionNotActiveError()

        return super().perform_create(serializer)

    def perform_update(self, serializer):
        """Guard: block update if score is finalized."""
        score = self.get_object()

        if (score.status == 'submitted'
                and not score.unlocked_for_correction):
            raise ScoreFinalizedError()

        # Also check session is still active for updates
        if score.station:
            session = self._get_station_session(score.station)
            if session and session.status not in ('in_progress', 'active'):
                raise SessionNotActiveError()

        return super().perform_update(serializer)

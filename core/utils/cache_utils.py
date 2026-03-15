"""
Caching utilities for frequently-queried, rarely-changing data.

Keys & timeouts:
  departments_list  → 30 min  (only changes when admin edits departments)
  examiner_stats    → 5 min   (counts, assigned-today)
  examiner_list     → 5 min   (full queryset list)
  session_detail_<id> → 2 min (paths, assignments for one session)

All cache keys are invalidated explicitly when the underlying data changes
(signals + view-level invalidation helpers below).
"""
import logging

from django.core.cache import cache

logger = logging.getLogger('osce.cache')

# ── TTLs (seconds) ─────────────────────────────────────────────────────────
DEPT_LIST_TTL        = 60 * 30   # 30 minutes
EXAMINER_STATS_TTL   = 60 * 5    # 5 minutes
EXAMINER_LIST_TTL    = 60 * 5    # 5 minutes
SESSION_DETAIL_TTL   = 60 * 2    # 2 minutes
DASHBOARD_STATS_TTL  = 60 * 5    # 5 minutes

# ── Cache key builders ──────────────────────────────────────────────────────
DEPT_LIST_KEY            = 'osce:dept_list'
EXAMINER_STATS_KEY       = 'osce:examiner_stats'
EXAMINER_LIST_KEY        = 'osce:examiner_list'
SESSION_DETAIL_KEY       = 'osce:session_detail:{session_id}'
DASHBOARD_STATS_KEY      = 'osce:dashboard_stats'
EXAM_DETAIL_KEY          = 'exam_detail_{exam_id}'


# ── Department helpers ─────────────────────────────────────────────────────
def get_departments():
    """Return all Department objects from cache, hitting DB on miss."""
    result = cache.get(DEPT_LIST_KEY)
    if result is None:
        from core.models import Department
        result = list(Department.objects.order_by('name'))
        cache.set(DEPT_LIST_KEY, result, DEPT_LIST_TTL)
        logger.debug('Cache MISS: departments loaded from DB (%d items)', len(result))
    return result


def invalidate_departments():
    """Call when departments are added/edited/deleted."""
    cache.delete(DEPT_LIST_KEY)
    logger.debug('Cache INVALIDATED: departments')


# ── Examiner helpers ────────────────────────────────────────────────────────
def invalidate_examiner_list():
    """Call when any examiner is created, updated, or deleted."""
    cache.delete_many([EXAMINER_LIST_KEY, EXAMINER_STATS_KEY])
    logger.debug('Cache INVALIDATED: examiner_list + examiner_stats')


# ── Session helpers ─────────────────────────────────────────────────────────
def get_session_detail_cache_key(session_id):
    return SESSION_DETAIL_KEY.format(session_id=session_id)


def invalidate_session_detail(session_id):
    """Call when session, its paths, assignments or students change."""
    cache.delete(get_session_detail_cache_key(session_id))
    logger.debug('Cache INVALIDATED: session_detail %s', session_id)


def invalidate_exam_detail(exam_id):
    """Call when sessions are created, deleted, or status-changed for an exam."""
    cache.delete(EXAM_DETAIL_KEY.format(exam_id=exam_id))
    logger.debug('Cache INVALIDATED: exam_detail %s', exam_id)


# ── Dashboard stats helpers ─────────────────────────────────────────────────
def invalidate_dashboard_stats():
    cache.delete(DASHBOARD_STATS_KEY)
    logger.debug('Cache INVALIDATED: dashboard_stats')

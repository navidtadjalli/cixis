"""Minimal private API boundary. Domain routes arrive in later tasks."""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_501_NOT_IMPLEMENTED,
)
from django.conf import settings

from internal.auth import (
    SESSION_HEADER,
    authenticate_role,
    channel_is_authenticated,
    get_session_registry,
    get_unlock_throttle,
)
from internal.permissions import require_role


def _unlock_client_key(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def unlock(request):
    if not channel_is_authenticated(request):
        return Response({"detail": "Authentication required."}, status=HTTP_401_UNAUTHORIZED)

    throttle = get_unlock_throttle()
    client_key = _unlock_client_key(request)
    retry_after = throttle.retry_after(client_key)
    if retry_after is not None:
        response = Response({"detail": "Unlock temporarily unavailable."}, status=HTTP_429_TOO_MANY_REQUESTS)
        response["Retry-After"] = str(retry_after)
        return response

    role = request.data.get("role") if isinstance(request.data, dict) else None
    password = request.data.get("password") if isinstance(request.data, dict) else None
    if not authenticate_role(role, password):
        throttle.record_failure(client_key)
        return Response({"detail": "Authentication failed."}, status=HTTP_401_UNAUTHORIZED)

    throttle.clear(client_key)
    token = get_session_registry().create(role)
    return Response({"session_token": token, "role": role})


@api_view(["POST"])
@require_role("supervisor", "manager", "god")
def lock(request):
    get_session_registry().revoke(request.META.get(SESSION_HEADER), terminate=True)
    return Response(status=HTTP_204_NO_CONTENT)


@api_view(["GET"])
@require_role("supervisor", "manager", "god")
def health(request):
    return Response({"status": "ok"})


def _roster_service():
    return getattr(settings, "INTERNAL_ROSTER_SERVICE", None)


def _attendance_service():
    return getattr(settings, "INTERNAL_ATTENDANCE_SERVICE", None)


def _member_response(member):
    return {
        "uuid": member.uuid,
        "name": member.name,
        "sort_order": member.sort_order,
        "is_active": member.is_active,
        "revision": member.revision,
    }


def _roster_error(error):
    from internal.services.roster import RosterPermissionError, RosterValidationError

    if isinstance(error, RosterPermissionError):
        return Response({"detail": "Not permitted."}, status=HTTP_403_FORBIDDEN)
    if isinstance(error, RosterValidationError):
        return Response({"detail": "Invalid roster input."}, status=HTTP_400_BAD_REQUEST)
    if isinstance(error, KeyError):
        return Response({"detail": "Roster member not found."}, status=HTTP_404_NOT_FOUND)
    raise error


@api_view(["GET", "POST"])
@require_role("supervisor", "manager")
def roster_collection(request):
    service = _roster_service()
    if service is None:
        return Response(
            {"detail": "Roster service is not available."},
            status=HTTP_501_NOT_IMPLEMENTED,
        )
    try:
        if request.method == "GET":
            members = service.list_members(status=request.query_params.get("status", "active"))
            return Response([_member_response(member) for member in members])
        member = service.create(
            name=request.data.get("name") if isinstance(request.data, dict) else None,
            sort_order=(
                request.data.get("sort_order") if isinstance(request.data, dict) else None
            ),
            actor_role=request.user.role,
        )
        return Response(_member_response(member), status=HTTP_201_CREATED)
    except (ValueError, PermissionError, KeyError) as error:
        return _roster_error(error)


@api_view(["PATCH", "DELETE"])
@require_role("supervisor", "manager")
def roster_member(request, member_uuid):
    service = _roster_service()
    if service is None:
        return Response(status=HTTP_501_NOT_IMPLEMENTED)
    try:
        if request.method == "DELETE":
            service.deactivate(str(member_uuid), actor_role=request.user.role)
            return Response(status=HTTP_204_NO_CONTENT)
        member = service.rename(
            str(member_uuid),
            name=request.data.get("name") if isinstance(request.data, dict) else None,
            actor_role=request.user.role,
        )
        return Response(_member_response(member), status=HTTP_200_OK)
    except (ValueError, PermissionError, KeyError) as error:
        return _roster_error(error)


@api_view(["POST"])
@require_role("manager")
def roster_reactivate(request, member_uuid):
    service = _roster_service()
    if service is None:
        return Response(status=HTTP_501_NOT_IMPLEMENTED)
    try:
        member = service.reactivate(str(member_uuid), actor_role=request.user.role)
        return Response(_member_response(member), status=HTTP_200_OK)
    except (ValueError, PermissionError, KeyError) as error:
        return _roster_error(error)


def _attendance_response(entry):
    return {
        "uuid": entry.uuid,
        "staff_uuid": entry.staff_uuid,
        "staff_name": entry.staff_name,
        "jalali_date": entry.jalali_date,
        "shift": entry.shift,
        "check_in_hour": entry.check_in_hour,
        "check_in_minute": entry.check_in_minute,
        "check_out_hour": entry.check_out_hour,
        "check_out_minute": entry.check_out_minute,
        "metrics": {
            "worked": entry.metrics.worked,
            "late": entry.metrics.late,
            "early": entry.metrics.early,
            "overtime": entry.metrics.overtime,
            "shifts": entry.metrics.shifts,
        },
        "revision": entry.revision,
    }


def _attendance_error(error):
    from internal.jalali import DateLockedError, JalaliValidationError
    from internal.services.attendance import (
        AttendanceConflictError,
        AttendanceDuplicateError,
        AttendancePermissionError,
        AttendanceValidationError,
    )

    if isinstance(error, AttendancePermissionError):
        return Response({"detail": "Not permitted."}, status=HTTP_403_FORBIDDEN)
    if isinstance(error, (AttendanceDuplicateError, AttendanceConflictError)):
        return Response({"detail": "Attendance conflict."}, status=HTTP_409_CONFLICT)
    if isinstance(
        error,
        (AttendanceValidationError, JalaliValidationError, DateLockedError),
    ):
        return Response({"detail": "Invalid attendance input."}, status=HTTP_400_BAD_REQUEST)
    if isinstance(error, KeyError):
        return Response({"detail": "Attendance not found."}, status=HTTP_404_NOT_FOUND)
    raise error


@api_view(["GET", "POST"])
@require_role("supervisor", "manager")
def attendance_collection(request):
    service = _attendance_service()
    if service is None:
        return Response(
            {"detail": "Attendance service is not available."},
            status=HTTP_501_NOT_IMPLEMENTED,
        )
    try:
        if request.method == "GET":
            entries = service.list_entries(
                jalali_date=request.query_params.get("jalali_date"),
                shift=request.query_params.get("shift"),
            )
            return Response([_attendance_response(entry) for entry in entries])
        data = request.data if isinstance(request.data, dict) else {}
        entry = service.create(
            staff_uuid=data.get("staff_uuid"),
            jalali_date=data.get("jalali_date"),
            shift=data.get("shift"),
            check_in_hour=data.get("check_in_hour"),
            check_in_minute=data.get("check_in_minute"),
            check_out_hour=data.get("check_out_hour"),
            check_out_minute=data.get("check_out_minute"),
            actor_role=request.user.role,
        )
        return Response(_attendance_response(entry), status=HTTP_201_CREATED)
    except (ValueError, PermissionError, KeyError) as error:
        return _attendance_error(error)


@api_view(["POST"])
@require_role("manager")
def attendance_correction_preview(request, attendance_uuid):
    service = _attendance_service()
    if service is None:
        return Response(status=HTTP_501_NOT_IMPLEMENTED)
    try:
        data = request.data if isinstance(request.data, dict) else {}
        preview = service.preview_correction(
            str(attendance_uuid),
            changes=data.get("changes"),
            delete=data.get("delete", False),
            reason=data.get("reason"),
            actor_role=request.user.role,
        )
        return Response(
            {
                "token": preview.token,
                "action": preview.action,
                "impact": list(preview.impact),
            },
            status=HTTP_200_OK,
        )
    except (ValueError, PermissionError, KeyError) as error:
        return _attendance_error(error)


@api_view(["POST"])
@require_role("manager")
def attendance_correction_confirm(request):
    service = _attendance_service()
    if service is None:
        return Response(status=HTTP_501_NOT_IMPLEMENTED)
    try:
        data = request.data if isinstance(request.data, dict) else {}
        result = service.confirm_correction(
            data.get("token"), actor_role=request.user.role
        )
        return Response(
            {
                "action": result.action,
                "entry": (
                    _attendance_response(result.entry)
                    if result.entry is not None
                    else None
                ),
            },
            status=HTTP_200_OK,
        )
    except (ValueError, PermissionError, KeyError) as error:
        return _attendance_error(error)

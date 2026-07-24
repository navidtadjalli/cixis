"""Majaz guest/door codes API: bulk range generation + per-code CRUD.

Standalone door list (Story 2), unrelated to the ordering/event system. The
bulk generator mirrors ``setup.bulk_event_codes``: inclusive numeric range,
Persian-digit tolerant, capped at ``MAX_BULK``, skipping codes already present.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import GuestCode
from ..serializers import GuestCodeSerializer

# Ceiling on one bulk call — matches setup.MAX_BULK.
MAX_BULK = 500

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def _fa_num(value: int) -> str:
    return str(value).translate(str.maketrans("0123456789", FA_DIGITS))


def _int_field(request, key, default=None):
    """Parse an int field, tolerating Persian digits typed on a Persian keyboard."""
    raw = str(request.data.get(key, "")).strip()
    if not raw:
        return default
    normalized = raw.translate(str.maketrans(FA_DIGITS, "0123456789"))
    try:
        return int(normalized)
    except ValueError:
        return None


class GuestCodeViewSet(viewsets.ModelViewSet):
    """List / retrieve / update / delete guest codes (inline row editing)."""

    serializer_class = GuestCodeSerializer
    queryset = GuestCode.objects.all()


@api_view(["POST"])
def bulk_guest_codes(request):
    """Create a guest code per number in ``prefix`` + [start, end], inclusive.

    Codes already present are skipped, so a double-submit adds nothing.
    """
    prefix = str(request.data.get("prefix", "")).strip()
    start = _int_field(request, "start")
    end = _int_field(request, "end")

    if start is None or end is None:
        return Response(
            {"detail": "شماره شروع و پایان باید عدد باشند."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if start > end:
        return Response(
            {"detail": "شماره شروع نباید بزرگ‌تر از شماره پایان باشد."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if end - start + 1 > MAX_BULK:
        return Response(
            {"detail": f"حداکثر {_fa_num(MAX_BULK)} کد در هر بار."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    labels = [f"{prefix}{number}" for number in range(start, end + 1)]
    taken = set(
        GuestCode.objects.filter(code__in=labels).values_list("code", flat=True)
    )
    last = (
        GuestCode.objects.order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
        or 0
    )

    fresh = [
        GuestCode(code=code, sort_order=last + offset)
        for offset, code in enumerate(
            (code for code in labels if code not in taken), start=1
        )
    ]
    GuestCode.objects.bulk_create(fresh)
    return Response(
        {"created": len(fresh), "skipped": len(labels) - len(fresh)},
        status=status.HTTP_201_CREATED,
    )

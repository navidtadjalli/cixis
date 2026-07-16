"""Setup tools: bulk-create tables and event codes, wipe tables or the catalog.

Every endpoint here re-verifies the day-closing (revenue) password against the
request body. The unlock token handed out by /revenue/unlock/ is never presented
back to the server, so the screen's password gate is a UI affordance only —
these routes are destructive and must stand on their own.

Deletes are hard, not the soft ``is_active`` flip used elsewhere: this is a
"hand the operator a blank app" tool, so the rows go. Order history survives
regardless — items keep ``product_name_snapshot``/``unit_price_snapshot`` and an
order's ``table``/``product`` FKs are SET_NULL.
"""
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .. import menu_seed, services
from ..models import Category, Order, Product, Table
from .misc import check_revenue_password

# Ceiling on one bulk call. Well past any real cafe, low enough that a fat
# finger in the range fields cannot spawn a million rows.
MAX_BULK = 500

# Bundled menu the load button seeds. Shipped as an electron-builder
# extraResource next to the backend dir; see menu_seed.menu_path.
MENU_FILE = "menu.majaz.json"

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def _fa_num(value: int) -> str:
    """12 -> '۱۲'. Matches the Persian-digit table names the app ships with."""
    return str(value).translate(str.maketrans("0123456789", FA_DIGITS))


def _denied():
    return Response(
        {"detail": "رمز عبور نادرست است."}, status=status.HTTP_401_UNAUTHORIZED
    )


def _authorized(request) -> bool:
    return check_revenue_password(str(request.data.get("password", "")))


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


@api_view(["POST"])
def wipe_tables(request):
    """Delete every table, plus any unsettled order still sitting on one.

    Those orders go rather than block the reset: an unsettled table order left
    behind would keep its slot in the register with no table to open it from.
    Orders already settled into a DayClosing are kept — the closing's totals are
    a snapshot, so they only lose the table FK (SET_NULL).
    """
    if not _authorized(request):
        return _denied()

    live = Order.objects.filter(day_closing__isnull=True, table__isnull=False)
    with transaction.atomic():
        deleted_orders = live.count()
        live.delete()
        deleted_tables = Table.objects.count()
        Table.objects.all().delete()
    return Response(
        {"deleted_tables": deleted_tables, "deleted_orders": deleted_orders}
    )


@api_view(["POST"])
def wipe_orders(request):
    """Delete every order — table orders and event codes alike.

    The register resets to zero. Items and payments cascade with their order.
    DayClosing rows survive: their totals are snapshots taken at close time, so
    past reports still read correctly with the underlying orders gone.
    """
    if not _authorized(request):
        return _denied()

    with transaction.atomic():
        deleted = Order.objects.count()
        Order.objects.all().delete()
    return Response({"deleted_orders": deleted})


@api_view(["POST"])
def wipe_menu(request):
    """Delete every product and category.

    Products go first: Category -> Product is PROTECT, so the reverse order
    would raise. Past order lines are unaffected — they carry name and price
    snapshots and their ``product`` FK is SET_NULL.
    """
    if not _authorized(request):
        return _denied()

    products = Product.objects.count()
    categories = Category.objects.count()
    with transaction.atomic():
        Product.objects.all().delete()
        Category.objects.all().delete()
    return Response({"deleted_products": products, "deleted_categories": categories})


@api_view(["POST"])
def load_menu(request):
    """Seed the bundled Majaz menu, adding only what is missing."""
    if not _authorized(request):
        return _denied()

    path = menu_seed.menu_path(MENU_FILE)
    if not path.exists():
        return Response(
            {"detail": "فایل منو در این نسخه موجود نیست."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
    return Response(menu_seed.seed_menu_from_file(path))


@api_view(["POST"])
def bulk_tables(request):
    """Create ``count`` tables named «میز ۱» … «میز N».

    Names already present are skipped, so a double-click adds nothing.
    """
    if not _authorized(request):
        return _denied()

    count = _int_field(request, "count")
    if count is None or count < 1:
        return Response(
            {"detail": "تعداد میزها باید عددی مثبت باشد."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if count > MAX_BULK:
        return Response(
            {"detail": f"حداکثر {_fa_num(MAX_BULK)} میز در هر بار."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing = set(Table.objects.values_list("name", flat=True))
    last = (
        Table.objects.order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
        or 0
    )

    names = [f"میز {_fa_num(i)}" for i in range(1, count + 1)]
    fresh = [
        Table(name=name, sort_order=last + offset)
        for offset, name in enumerate(
            (name for name in names if name not in existing), start=1
        )
    ]
    Table.objects.bulk_create(fresh)
    return Response(
        {"created": len(fresh), "skipped": count - len(fresh)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def bulk_event_codes(request):
    """Create a preset event order per code in ``prefix`` + [start, end].

    The range is inclusive at both ends. Codes duplicating an already-active
    event order are skipped. Each row is an ordinary event order flagged
    ``is_preset``, which keeps it alive when the cashier backs out of it empty
    and keeps it out of the day-closing register until it is used.
    """
    if not _authorized(request):
        return _denied()

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
        Order.objects.filter(
            mode=Order.Mode.EVENT,
            status__in=services.ACTIVE_STATUSES,
            event_customer_label__in=labels,
        ).values_list("event_customer_label", flat=True)
    )

    today = services.business_today()
    created = 0
    with transaction.atomic():
        for label in labels:
            if label in taken:
                continue
            # Not bulk_create: Order.save() assigns the sequential order_number.
            Order.objects.create(
                mode=Order.Mode.EVENT,
                event_customer_label=label,
                is_preset=True,
                status=Order.Status.OPEN,
                business_date=today,
            )
            created += 1

    return Response(
        {"created": created, "skipped": len(labels) - created},
        status=status.HTTP_201_CREATED,
    )

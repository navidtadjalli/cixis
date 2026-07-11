"""Menu publish logic: render the active menu to static HTML and upload it to the
QR-menu bucket. Every attempt is recorded as a MenuPublishRecord."""
import time

from django.template.loader import render_to_string
from django.utils import timezone

from .models import AppSetting, Category, MenuPublishRecord
from .storage import storage_config, upload_html, website_url

# The bucket is served as a static website, so the menu always lands at the root.
MENU_OBJECT_NAME = "index.html"


def _setting(key, default=""):
    obj = AppSetting.objects.filter(key=key).first()
    return obj.value if obj else default


# Signature hue per category, cycled by position. Only the hue varies — the menu
# template pins saturation/lightness so every category stays a readable dark tint.
CATEGORY_HUES = [38, 14, 350, 320, 275, 225, 200, 172, 150, 128, 95, 50]


def build_menu_payload() -> dict:
    """Snapshot active categories with their active products (ordered).

    Unavailable products are included but flagged; inactive products are excluded.
    """
    categories = []
    for i, cat in enumerate(
        Category.objects.filter(is_active=True).order_by("sort_order", "id")
    ):
        products = [
            {
                "name": p.name,
                "price": p.price,
                "is_available": p.is_available,
                "sort_order": p.sort_order,
            }
            for p in cat.products.filter(
                is_active=True, is_publishable=True
            ).order_by("sort_order", "id")
        ]
        categories.append(
            {
                "name": cat.name,
                "sort_order": cat.sort_order,
                "hue": CATEGORY_HUES[i % len(CATEGORY_HUES)],
                "products": products,
            }
        )

    return {
        "cafe_slug": _setting("cafe_slug", "cixis-cafe"),
        "cafe_name": _setting("cafe_name", "خروج"),
        "version": str(int(time.time())),
        "published_at": timezone.now().isoformat(),
        "categories": categories,
    }


def render_menu_html(payload: dict) -> str:
    """Render the payload into the standalone page customers see."""
    return render_to_string(
        "pos/menu.html",
        {
            "cafe_name": payload["cafe_name"],
            "categories": payload["categories"],
            "version": payload["version"],
            "published_at": payload["published_at"],
        },
    )


def publish_menu() -> dict:
    """Render + upload the menu. Returns {success, published_at, url?, error?}.

    Failures never raise — they are captured into the publish record so the UI can
    surface them without the request 500ing.
    """
    payload = build_menu_payload()
    now = timezone.now()

    record = MenuPublishRecord(
        version=payload["version"],
        payload_snapshot=payload,
        status=MenuPublishRecord.Status.PENDING,
    )

    try:
        config = storage_config()
        upload_html(MENU_OBJECT_NAME, render_menu_html(payload), config)
    except Exception as exc:
        record.status = MenuPublishRecord.Status.FAILED
        record.error_message = str(exc)[:500]
        record.save()
        return {"success": False, "published_at": None, "error": str(exc)}

    record.status = MenuPublishRecord.Status.SUCCESS
    record.published_at = now
    record.save()
    return {
        "success": True,
        "published_at": now.isoformat(),
        "url": website_url(config),
    }

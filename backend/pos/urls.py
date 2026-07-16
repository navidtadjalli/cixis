from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import api_root, day_closing, misc, reports, setup
from .views.menu import CategoryViewSet, ProductViewSet
from .views.orders import OrderItemViewSet, OrderViewSet
from .views.resources import ResourcePurchaseListCreate
from .views.tables import TableViewSet

router = DefaultRouter()
router.register("tables", TableViewSet, basename="table")
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")
router.register("order-items", OrderItemViewSet, basename="order-item")

urlpatterns = [
    path("", api_root, name="api-root"),
    path("day-closing/preview/", day_closing.preview, name="day-closing-preview"),
    path("day-closing/close/", day_closing.close, name="day-closing-close"),
    path("reports/monthly/", reports.monthly, name="reports-monthly"),
    path("reports/range/", reports.date_range, name="reports-range"),
    path(
        "resources/purchases/",
        ResourcePurchaseListCreate.as_view(),
        name="resource-purchases",
    ),
    path("menu/publish/", misc.menu_publish, name="menu-publish"),
    path("sync/retry/", misc.sync_retry, name="sync-retry"),
    path("revenue/unlock/", misc.revenue_unlock, name="revenue-unlock"),
    path(
        "revenue/password/",
        misc.revenue_change_password,
        name="revenue-change-password",
    ),
    path(
        "settings/publish/unlock/",
        misc.publish_settings_unlock,
        name="publish-settings-unlock",
    ),
    path(
        "settings/publish/",
        misc.publish_settings_save,
        name="publish-settings-save",
    ),
    path("setup/tables/wipe/", setup.wipe_tables, name="setup-wipe-tables"),
    path("setup/orders/wipe/", setup.wipe_orders, name="setup-wipe-orders"),
    path("setup/menu/wipe/", setup.wipe_menu, name="setup-wipe-menu"),
    path("setup/menu/load/", setup.load_menu, name="setup-load-menu"),
    path("setup/tables/bulk/", setup.bulk_tables, name="setup-bulk-tables"),
    path(
        "setup/event-codes/bulk/",
        setup.bulk_event_codes,
        name="setup-bulk-event-codes",
    ),
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import api_root, day_closing, misc, reports
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
    path("", include(router.urls)),
]

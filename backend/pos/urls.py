from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import api_root
from .views import day_closing
from .views.menu import CategoryViewSet, ProductViewSet
from .views.orders import OrderItemViewSet, OrderViewSet
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
    path("", include(router.urls)),
]

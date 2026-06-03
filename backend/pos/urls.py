from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import api_root
from .views.menu import CategoryViewSet, ProductViewSet
from .views.tables import TableViewSet

router = DefaultRouter()
router.register("tables", TableViewSet, basename="table")
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = [
    path("", api_root, name="api-root"),
    path("", include(router.urls)),
]

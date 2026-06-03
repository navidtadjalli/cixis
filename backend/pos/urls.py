from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import api_root
from .views.tables import TableViewSet

router = DefaultRouter()
router.register("tables", TableViewSet, basename="table")

urlpatterns = [
    path("", api_root, name="api-root"),
    path("", include(router.urls)),
]

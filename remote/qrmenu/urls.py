from django.urls import path

from .views import DayClosingSyncCreateView, MenuSnapshotCreateView, PublicMenuJsonView, public_menu_page


urlpatterns = [
    path("", public_menu_page, name="public-menu-page"),
    path("api/public/menu/<slug:cafe_slug>/", PublicMenuJsonView.as_view(), name="public-menu-json"),
    path("api/private/menu-snapshots/", MenuSnapshotCreateView.as_view(), name="private-menu-snapshots"),
    path("api/private/day-closing-sync/", DayClosingSyncCreateView.as_view(), name="private-day-closing-sync"),
]

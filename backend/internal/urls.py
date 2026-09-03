from django.urls import path

from internal import views


urlpatterns = [
    path("unlock/", views.unlock, name="internal-unlock"),
    path("lock/", views.lock, name="internal-lock"),
    path("health/", views.health, name="internal-health"),
    path("roster/", views.roster_collection, name="internal-roster"),
    path("roster/<uuid:member_uuid>/", views.roster_member, name="internal-roster-member"),
    path(
        "roster/<uuid:member_uuid>/reactivate/",
        views.roster_reactivate,
        name="internal-roster-reactivate",
    ),
    path("attendance/", views.attendance_collection, name="internal-attendance"),
    path(
        "attendance/<uuid:attendance_uuid>/corrections/preview/",
        views.attendance_correction_preview,
        name="internal-attendance-correction-preview",
    ),
    path(
        "attendance/corrections/confirm/",
        views.attendance_correction_confirm,
        name="internal-attendance-correction-confirm",
    ),
]

from django.urls import path

from internal import views


urlpatterns = [
    path("unlock/", views.unlock, name="internal-unlock"),
    path("lock/", views.lock, name="internal-lock"),
    path("health/", views.health, name="internal-health"),
    path("roster/", views.roster_placeholder, name="internal-roster-placeholder"),
]

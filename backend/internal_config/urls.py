from django.urls import include, path


urlpatterns = [
    path("api/internal/", include("internal.urls")),
]

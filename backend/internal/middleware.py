"""Reject browser-origin requests; Electron main performs private API traffic."""
from django.http import JsonResponse


class RejectInternalOriginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/internal/") and (
            request.META.get("HTTP_ORIGIN")
            or request.META.get("HTTP_ACCESS_CONTROL_REQUEST_METHOD")
        ):
            return JsonResponse({"detail": "Not permitted."}, status=403)
        return self.get_response(request)

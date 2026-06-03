from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_root(request):
    """Health/root endpoint. Used by the Electron shell to confirm the backend is up."""
    return Response({"app": "cixis", "status": "ok", "version": "1.0.0"})

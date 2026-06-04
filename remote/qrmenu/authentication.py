from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class ApiKeyUser:
    is_authenticated = True
    is_anonymous = False
    username = "api-key"

    def __str__(self):
        return self.username


class ApiKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        raw_header = get_authorization_header(request).decode("utf-8")
        parts = raw_header.split()

        if len(parts) != 2 or parts[0] != self.keyword:
            raise AuthenticationFailed("Missing or invalid API key.")

        if parts[1] != settings.CIXIS_API_KEY:
            raise AuthenticationFailed("Missing or invalid API key.")

        return (ApiKeyUser(), None)

    def authenticate_header(self, request):
        return self.keyword

import base64
import binascii
import hmac
import os

from django.http import HttpResponse


class PreviewAuthentication:
    def __init__(self, get_response):
        self.get_response = get_response
        self.password = os.environ['PREVIEW_PASSWORD']

    def __call__(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        try:
            scheme, token = header.split(' ', 1)
            credentials = base64.b64decode(token, validate=True).decode('utf-8')
            username, password = credentials.split(':', 1)
            valid = scheme.lower() == 'basic' and hmac.compare_digest(username, 'client') and hmac.compare_digest(password, self.password)
        except (ValueError, UnicodeError, binascii.Error):
            valid = False
        if not valid:
            response = HttpResponse('Authentication required', status=401)
            response['WWW-Authenticate'] = 'Basic realm="Store preview", charset="UTF-8"'
            return response
        return self.get_response(request)

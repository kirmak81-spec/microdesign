from .settings import *  # noqa: F403

FORCE_SCRIPT_NAME = '/shop'
STATIC_URL = 'static/'
MEDIA_URL = 'media/'
ROOT_URLCONF = 'config.preview_urls'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
MIDDLEWARE = ['config.preview_auth.PreviewAuthentication'] + MIDDLEWARE

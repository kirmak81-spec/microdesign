import mimetypes

mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/avif', '.avif')

from django.conf import settings
from django.contrib.staticfiles.views import serve as serve_static
from django.urls import path
from django.views.static import serve as serve_media
from .urls import urlpatterns

urlpatterns = urlpatterns + [
    path('static/<path:path>', serve_static, {'insecure': True}),
    path('media/<path:path>', serve_media, {'document_root': settings.MEDIA_ROOT}),
]

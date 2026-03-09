from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

import core.admin  # noqa: F401 — patches admin.site

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dicom/', include('dicom.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

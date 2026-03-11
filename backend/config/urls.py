import re

from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path, re_path

from .frontend import FrontendDistView, MediaFileView

media_prefix = (settings.MEDIA_URL or "/media/").lstrip("/").rstrip("/")
frontend_excluded_prefixes = [r"api(?:/|$)", r"admin(?:/|$)", r"static(?:/|$)"]
if media_prefix:
    frontend_excluded_prefixes.append(rf"{re.escape(media_prefix)}(?:/|$)")
excluded_prefix_pattern = "|".join(frontend_excluded_prefixes)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("wiki.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    if media_prefix:
        urlpatterns += [
            re_path(rf"^{re.escape(media_prefix)}/(?P<path>.+)$", MediaFileView.as_view(), name="media-file"),
        ]

urlpatterns += [
    re_path(rf"^(?P<path>(?!(?:{excluded_prefix_pattern})).*)$", FrontendDistView.as_view(), name="frontend-dist"),
]

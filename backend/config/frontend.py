import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.views import View


class SafeFileView(View):
    cache_forever = False

    def serve_file(self, root_dir: Path, relative_path: str):
        candidate = self._safe_join(root_dir, relative_path)
        if not candidate.is_file():
            raise Http404("File not found.")
        return self._build_response(candidate, cache_forever=self.cache_forever)

    def _safe_join(self, base_dir: Path, relative_path: str) -> Path:
        try:
            candidate = (base_dir / relative_path).resolve()
            candidate.relative_to(base_dir)
        except ValueError:
            raise Http404("Invalid file path.") from None
        return candidate

    def _build_response(self, file_path: Path, *, cache_forever: bool):
        content_type, encoding = mimetypes.guess_type(str(file_path))
        response = FileResponse(file_path.open("rb"), content_type=content_type or "application/octet-stream")
        if encoding:
            response["Content-Encoding"] = encoding
        response["Cache-Control"] = (
            "public, max-age=31536000, immutable" if cache_forever else "no-cache, no-store, must-revalidate"
        )
        return response


class FrontendDistView(SafeFileView):
    index_name = "index.html"

    def get(self, request, path=""):
        if not getattr(settings, "SERVE_FRONTEND", False):
            raise Http404("Frontend hosting is disabled.")

        dist_root = Path(getattr(settings, "FRONTEND_DIST_DIR", "")).resolve()
        if not dist_root.exists():
            raise Http404("Frontend dist directory does not exist.")

        relative_path = str(path or "").lstrip("/")
        if relative_path:
            candidate = self._safe_join(dist_root, relative_path)
            if candidate.is_file():
                return self._build_response(candidate, cache_forever=relative_path != self.index_name)
            if Path(relative_path).suffix:
                raise Http404("Frontend asset not found.")

        index_file = dist_root / self.index_name
        if not index_file.is_file():
            raise Http404("Frontend index.html was not found.")
        return self._build_response(index_file, cache_forever=False)


class MediaFileView(SafeFileView):
    cache_forever = False

    def _host_from_value(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        parsed = urlparse(text if "://" in text else f"//{text}")
        return (parsed.hostname or "").lower()

    def _is_hotlink_protected(self, relative_path: str) -> bool:
        if not bool(getattr(settings, "MEDIA_HOTLINK_PROTECTION", False)):
            return False
        protected_prefixes = getattr(settings, "MEDIA_HOTLINK_PROTECTED_PREFIXES", ())
        if isinstance(protected_prefixes, str):
            protected_prefixes = [protected_prefixes]
        relative = str(relative_path or "").lstrip("/")
        for prefix in protected_prefixes:
            clean_prefix = str(prefix or "").strip().strip("/")
            if not clean_prefix:
                continue
            if relative == clean_prefix or relative.startswith(f"{clean_prefix}/"):
                return True
        return False

    def _is_external_referer(self, request) -> bool:
        referer = str(request.META.get("HTTP_REFERER") or "").strip()
        if not referer:
            return False
        referer_host = self._host_from_value(referer)
        if not referer_host:
            return False

        allowed_hosts = {
            self._host_from_value(request.get_host()),
            *[
                self._host_from_value(item)
                for item in getattr(settings, "MEDIA_HOTLINK_ALLOWED_HOSTS", [])
            ],
            *[
                self._host_from_value(item)
                for item in getattr(settings, "ALLOWED_HOSTS", [])
                if item and item != "*"
            ],
        }
        allowed_hosts.discard("")
        return referer_host not in allowed_hosts

    def get(self, request, path=""):
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if not media_root.exists():
            raise Http404("Media directory does not exist.")
        relative_path = str(path or "").lstrip("/")
        if not relative_path:
            raise Http404("Media file path is required.")
        if self._is_hotlink_protected(relative_path) and self._is_external_referer(request):
            return HttpResponseForbidden("Hotlinking is not allowed.")
        return self.serve_file(media_root, relative_path)

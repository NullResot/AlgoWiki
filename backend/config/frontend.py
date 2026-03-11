import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
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

    def get(self, request, path=""):
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if not media_root.exists():
            raise Http404("Media directory does not exist.")
        relative_path = str(path or "").lstrip("/")
        if not relative_path:
            raise Http404("Media file path is required.")
        return self.serve_file(media_root, relative_path)

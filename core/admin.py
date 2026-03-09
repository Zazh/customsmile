from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import Http404

from company.models import Company, Domain

User = get_user_model()

SHARED_MODELS = {User, Company, Domain, Group}
SHARED_MODEL_NAMES = {m.__name__ for m in SHARED_MODELS}
BLOCKED_APP_LABELS = {m._meta.app_label for m in SHARED_MODELS}


class TenantAwareAdminSite(admin.AdminSite):
    """Single admin site that hides and blocks shared models on tenant schemas."""

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if not self._is_public_schema(request):
            filtered = []
            for app in app_list:
                app["models"] = [
                    m for m in app["models"]
                    if m.get("object_name") not in SHARED_MODEL_NAMES
                ]
                if app["models"]:
                    filtered.append(app)
            return filtered
        return app_list

    def admin_view(self, view, cacheable=False):
        inner = super().admin_view(view, cacheable)

        def wrapper(request, *args, **kwargs):
            if not self._is_public_schema(request):
                path = request.path
                for label in BLOCKED_APP_LABELS:
                    if f"/admin/{label}/" in path:
                        raise Http404
            return inner(request, *args, **kwargs)

        wrapper.admin_site = self
        return wrapper

    def _is_public_schema(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant:
            return tenant.schema_name == "public"
        return True


# Replace the default admin site
admin.site.__class__ = TenantAwareAdminSite

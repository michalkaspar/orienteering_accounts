from django.contrib.auth.mixins import AccessMixin


class PermissionsRequiredMixin(AccessMixin):
    """Verify that the current user has all specified permissions."""
    permissions_required = []

    def get_permissions_required(self):
        perms = self.permissions_required

        if not perms:
            raise NotImplementedError("Permissions definition required in 'permissions_required' attribute.")

        return perms

    def has_permission(self):
        """
        Override this method to customize the way permissions are checked.
        """
        perms = self.get_permissions_required()

        if perms:
            return any(perm(self.request.user) for perm in perms)

        return False

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission():
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

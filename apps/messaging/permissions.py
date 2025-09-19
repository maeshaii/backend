from rest_framework.permissions import BasePermission


class IsAlumniOrOJT(BasePermission):
    message = 'Messaging is restricted to alumni, OJT, admin, or PESO users.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'account_type', None):
            return False
        account_type = user.account_type
        return bool(
            getattr(account_type, 'user', False)
            or getattr(account_type, 'ojt', False)
            or getattr(account_type, 'admin', False)
            or getattr(account_type, 'peso', False)
            or getattr(account_type, 'coordinator', False)
        )

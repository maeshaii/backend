from rest_framework.permissions import BasePermission


class IsAlumniOrOJT(BasePermission):
	message = 'Messaging is restricted to alumni and OJT users.'

	def has_permission(self, request, view):
		user = getattr(request, 'user', None)
		if not user or not getattr(user, 'account_type', None):
			return False
		account_type = user.account_type
		return bool(getattr(account_type, 'alumni', False) or getattr(account_type, 'ojt', False))

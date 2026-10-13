from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q


def find_user_by_credentials(identifier, password):
    """The user whose username or email matches `identifier` (case-insensitively)
    and whose password is `password`, or None. Active or not -- callers decide.

    Case-insensitive because sign-ups used to store the email exactly as typed
    while mobile login lowercased it. Iterates rather than .get(): older data can
    hold case-variant duplicates (Foo@x.com and foo@x.com), and the password
    picks out the right one.
    """
    if not identifier or not password:
        return None
    candidates = User.objects.filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier)
    ).order_by('id')
    for user in candidates:
        if user.check_password(password):
            return user
    return None


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = find_user_by_credentials(username, password)
        if user is not None and self.user_can_authenticate(user):
            return user
        return None

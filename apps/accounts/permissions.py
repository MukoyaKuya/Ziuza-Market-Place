from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import PermissionDenied


def ensure_authenticated(*, actor: AbstractBaseUser | None) -> AbstractBaseUser:
    """Require a logged-in user for account mutations and private reads."""
    if actor is None or not getattr(actor, 'is_authenticated', False):
        raise PermissionDenied('Authentication required.')
    return actor


def ensure_address_owner(*, actor: AbstractBaseUser, address) -> None:
    """Actor must own the address. Prefer filtering by user in selectors/services."""
    ensure_authenticated(actor=actor)
    if address.user_id != actor.id:
        raise PermissionDenied('You are not authorized to access this address.')

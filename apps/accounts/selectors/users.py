from django.contrib.auth import get_user_model

User = get_user_model()


def get_user_by_email(*, email: str) -> User | None:
    email = (email or '').strip().lower()
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()

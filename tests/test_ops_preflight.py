from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.mark.django_db
@override_settings(REQUIRE_EMAIL_VERIFICATION=False)
def test_ops_preflight_passes_with_database_migrations_and_compiled_css():
    output = StringIO()

    call_command('ops_preflight', stdout=output)

    assert 'Operational preflight passed' in output.getvalue()


@pytest.mark.django_db
@override_settings(REQUIRE_EMAIL_VERIFICATION=False)
def test_ops_preflight_rejects_missing_compiled_css(tmp_path):
    with override_settings(BASE_DIR=tmp_path):
        with pytest.raises(CommandError, match=r'styles\.css'):
            call_command('ops_preflight')


@pytest.mark.django_db
@override_settings(
    REQUIRE_EMAIL_VERIFICATION=True,
    EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
)
def test_ops_preflight_rejects_non_delivery_email_backend():
    with pytest.raises(CommandError, match='delivery-capable EMAIL_BACKEND'):
        call_command('ops_preflight')

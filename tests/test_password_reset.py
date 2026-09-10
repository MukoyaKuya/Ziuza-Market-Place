"""Password reset: email dispatch, link consumption, and invalidation on use."""

import re

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.urls import reverse

User = get_user_model()
PASSWORD = 'SecurePassword123!'
NEW_PASSWORD = 'NewSecurePassword456!'


@pytest.fixture
def user(db):
    return User.objects.create_user(email='reset-me@ziuza.co.ke', password=PASSWORD, display_name='Resetter')


def _reset_link(message) -> str:
    match = re.search(r'(https?://[^/]+)?(/account/password-reset/[^/\s]+/[^/\s]+/)', message.body)
    assert match, f'No reset link found in email body:\n{message.body}'
    return match.group(2)


def test_reset_request_sends_email_with_link(client, user):
    response = client.post(reverse('accounts:password_reset'), {'email': user.email})

    assert response.status_code == 302
    assert response.url == reverse('accounts:password_reset_done')
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [user.email]
    assert 'reset' in message.subject.lower()
    assert '/account/password-reset/' in message.body


def test_reset_request_for_unknown_email_does_not_reveal_accounts(client, db):
    response = client.post(reverse('accounts:password_reset'), {'email': 'ghost@ziuza.co.ke'})

    assert response.status_code == 302
    assert response.url == reverse('accounts:password_reset_done')
    assert len(mail.outbox) == 0


def test_full_reset_flow_changes_password(client, user):
    client.post(reverse('accounts:password_reset'), {'email': user.email})
    link = _reset_link(mail.outbox[0])

    # Django swaps the one-time token for a session-backed "set-password" URL.
    redirect = client.get(link)
    assert redirect.status_code == 302
    set_password_url = redirect.url

    page = client.get(set_password_url)
    assert page.status_code == 200
    assert 'Choose a new password' in page.content.decode()

    response = client.post(set_password_url, {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
    assert response.status_code == 302
    assert response.url == reverse('accounts:password_reset_complete')

    assert authenticate(username=user.email, password=NEW_PASSWORD) is not None
    assert authenticate(username=user.email, password=PASSWORD) is None


def test_reset_link_single_use(client, user):
    client.post(reverse('accounts:password_reset'), {'email': user.email})
    link = _reset_link(mail.outbox[0])
    set_password_url = client.get(link).url
    client.post(set_password_url, {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})

    # The consumed link no longer shows the set-password form.
    page = client.get(link)
    content = page.content.decode()
    assert 'invalid or has expired' in content
    assert 'Set new password' not in content


def test_tampered_token_shows_invalid_page(client, user):
    client.post(reverse('accounts:password_reset'), {'email': user.email})
    link = _reset_link(mail.outbox[0])
    uid, _token = link.strip('/').rsplit('/', 2)[-2:]

    page = client.get(reverse('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': 'tampered'}))
    assert 'invalid or has expired' in page.content.decode()


def test_login_page_links_to_reset_flow(client, db):
    page = client.get(reverse('accounts:login'))
    assert reverse('accounts:password_reset') in page.content.decode()

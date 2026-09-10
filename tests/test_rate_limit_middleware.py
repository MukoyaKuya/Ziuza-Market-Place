from unittest.mock import patch

from django.test import RequestFactory, override_settings

from apps.core.middleware import SimpleRateLimitMiddleware


def _rate_limit_key(*, remote_addr='127.0.0.1', client_ip='', trusted_proxies=()) -> str:
    request = RequestFactory().get(
        '/account/login/',
        REMOTE_ADDR=remote_addr,
        HTTP_CF_CONNECTING_IP=client_ip,
    )
    middleware = SimpleRateLimitMiddleware(lambda _request: None)
    with override_settings(
        TRUSTED_PROXY_IPS=trusted_proxies,
        TRUSTED_CLIENT_IP_HEADER='HTTP_CF_CONNECTING_IP',
    ):
        with patch('apps.core.middleware.cache.add', return_value=True) as cache_add:
            assert middleware._allow(request, '/account/login/', 20, 60)
    return cache_add.call_args.args[0]


def test_rate_limit_ignores_client_ip_header_when_proxy_is_not_trusted():
    key = _rate_limit_key(client_ip='203.0.113.10')

    assert ':127.0.0.1:' in key


def test_rate_limit_uses_client_ip_header_from_trusted_proxy():
    key = _rate_limit_key(client_ip='203.0.113.10', trusted_proxies=['127.0.0.1'])

    assert ':203.0.113.10:' in key


def test_rate_limit_rejects_malformed_client_ip():
    key = _rate_limit_key(client_ip='spoofed-value', trusted_proxies=['127.0.0.1'])

    assert ':127.0.0.1:' in key


def test_rate_limit_does_not_trust_spoofed_forwarded_chain():
    request = RequestFactory().get(
        '/account/login/',
        REMOTE_ADDR='127.0.0.1',
        HTTP_X_FORWARDED_FOR='198.51.100.9, 203.0.113.10',
    )
    middleware = SimpleRateLimitMiddleware(lambda _request: None)
    with override_settings(
        TRUSTED_PROXY_IPS=['127.0.0.1'],
        TRUSTED_CLIENT_IP_HEADER='HTTP_CF_CONNECTING_IP',
    ):
        with patch('apps.core.middleware.cache.add', return_value=True) as cache_add:
            assert middleware._allow(request, '/account/login/', 20, 60)

    assert ':127.0.0.1:' in cache_add.call_args.args[0]

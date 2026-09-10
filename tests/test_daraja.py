import base64
import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.marketplace.payments.daraja import DarajaClient, DarajaConfig, DarajaError, normalize_phone


class JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def config(**overrides):
    values = {
        'consumer_key': 'consumer-key',
        'consumer_secret': 'consumer-secret',
        'shortcode': '174379',
        'passkey': 'sandbox-passkey',
        'callback_url': 'https://example.com/payments/callback/mpesa/',
        'callback_token': 'callback-secret',
    }
    values.update(overrides)
    return DarajaConfig(**values)


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [('0712345678', '254712345678'), ('712345678', '254712345678'), ('254712345678', '254712345678')],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_phone_rejects_invalid_number():
    with pytest.raises(ValueError, match='valid Kenyan'):
        normalize_phone('1234')


@patch('apps.marketplace.payments.daraja.urlopen')
def test_stk_push_uses_oauth_and_authenticated_callback(mock_urlopen):
    mock_urlopen.side_effect = [
        JsonResponse({'access_token': 'access-token'}),
        JsonResponse({
            'ResponseCode': '0',
            'MerchantRequestID': 'merchant-id',
            'CheckoutRequestID': 'checkout-id',
            'CustomerMessage': 'Success',
        }),
    ]
    response = DarajaClient(config()).stk_push(
        phone='0712345678',
        amount=Decimal('2800.00'),
        account_reference='ZIU-12345678',
        description='Order ZIU-12345678',
    )

    oauth_request = mock_urlopen.call_args_list[0].args[0]
    expected_basic = base64.b64encode(b'consumer-key:consumer-secret').decode()
    assert oauth_request.get_header('Authorization') == f'Basic {expected_basic}'
    assert oauth_request.full_url.startswith('https://sandbox.safaricom.co.ke/oauth/v1/generate')

    stk_request = mock_urlopen.call_args_list[1].args[0]
    payload = json.loads(stk_request.data)
    assert stk_request.get_header('Authorization') == 'Bearer access-token'
    assert payload['PhoneNumber'] == '254712345678'
    assert payload['Amount'] == 2800
    assert payload['CallBackURL'].endswith('?token=callback-secret')
    assert response['CheckoutRequestID'] == 'checkout-id'


def test_stk_push_rejects_fractional_kes_before_network_call():
    with pytest.raises(ValueError, match='whole number'):
        DarajaClient(config()).stk_push(
            phone='0712345678',
            amount=Decimal('10.50'),
            account_reference='ZIU-1',
            description='Order',
        )


@patch('apps.marketplace.payments.daraja.urlopen')
def test_stk_query_uses_authenticated_daraja_endpoint(mock_urlopen):
    mock_urlopen.side_effect = [
        JsonResponse({'access_token': 'access-token'}),
        JsonResponse({'ResponseCode': '0', 'ResultCode': '0', 'ResultDesc': 'Success'}),
    ]

    response = DarajaClient(config()).stk_query(checkout_request_id='ws_CO_123')

    query_request = mock_urlopen.call_args_list[1].args[0]
    payload = json.loads(query_request.data)
    assert query_request.full_url.endswith('/mpesa/stkpushquery/v1/query')
    assert query_request.get_header('Authorization') == 'Bearer access-token'
    assert payload['CheckoutRequestID'] == 'ws_CO_123'
    assert response['ResultCode'] == '0'


@patch('apps.marketplace.payments.daraja.urlopen')
def test_stk_query_rejects_response_without_final_result(mock_urlopen):
    mock_urlopen.side_effect = [
        JsonResponse({'access_token': 'access-token'}),
        JsonResponse({'ResponseCode': '0', 'ResponseDescription': 'Still processing'}),
    ]

    with pytest.raises(DarajaError, match='did not return a final result'):
        DarajaClient(config()).stk_query(checkout_request_id='ws_CO_123')

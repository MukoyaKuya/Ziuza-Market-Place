"""Minimal Daraja OAuth and Lipa na M-Pesa Online client."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.utils import timezone


class DarajaError(RuntimeError):
    pass


def normalize_phone(phone: str) -> str:
    value = ''.join(character for character in str(phone) if character.isdigit())
    if value.startswith('0') and len(value) == 10:
        value = f'254{value[1:]}'
    elif value.startswith('7') and len(value) == 9:
        value = f'254{value}'
    if not (value.startswith('254') and len(value) == 12):
        raise ValueError('Enter a valid Kenyan M-Pesa number, for example 0712345678.')
    return value


@dataclass(frozen=True)
class DarajaConfig:
    consumer_key: str
    consumer_secret: str
    shortcode: str
    passkey: str
    callback_url: str
    callback_token: str = ''
    live: bool = False
    timeout: int = 15
    transaction_type: str = 'CustomerPayBillOnline'

    @property
    def base_url(self) -> str:
        return 'https://api.safaricom.co.ke' if self.live else 'https://sandbox.safaricom.co.ke'

    @property
    def authenticated_callback_url(self) -> str:
        if not self.callback_token:
            return self.callback_url
        parts = urlsplit(self.callback_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['token'] = self.callback_token
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class DarajaClient:
    def __init__(self, config: DarajaConfig):
        self.config = config

    def _request(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')[:1000]
            raise DarajaError(f'Daraja returned HTTP {exc.code}: {body}') from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DarajaError('Unable to communicate with Daraja.') from exc

    def access_token(self) -> str:
        credentials = base64.b64encode(
            f'{self.config.consumer_key}:{self.config.consumer_secret}'.encode()
        ).decode()
        request = Request(
            f'{self.config.base_url}/oauth/v1/generate?grant_type=client_credentials',
            headers={'Authorization': f'Basic {credentials}', 'Accept': 'application/json'},
        )
        token = self._request(request).get('access_token')
        if not token:
            raise DarajaError('Daraja OAuth response did not contain an access token.')
        return token

    def _timestamp_and_password(self) -> tuple[str, str]:
        timestamp = timezone.localtime(timezone.now()).strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f'{self.config.shortcode}{self.config.passkey}{timestamp}'.encode()
        ).decode()
        return timestamp, password

    def stk_push(self, *, phone: str, amount: Decimal, account_reference: str, description: str) -> dict:
        phone = normalize_phone(phone)
        if amount != amount.to_integral_value():
            raise ValueError('M-Pesa STK Push amount must be a whole number of Kenyan shillings.')
        timestamp, password = self._timestamp_and_password()
        payload = {
            'BusinessShortCode': self.config.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': self.config.transaction_type,
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.config.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': self.config.authenticated_callback_url,
            'AccountReference': account_reference[:12],
            'TransactionDesc': description[:13],
        }
        request = Request(
            f'{self.config.base_url}/mpesa/stkpush/v1/processrequest',
            data=json.dumps(payload).encode(),
            method='POST',
            headers={
                'Authorization': f'Bearer {self.access_token()}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        response = self._request(request)
        if str(response.get('ResponseCode')) != '0' or not response.get('CheckoutRequestID'):
            raise DarajaError(response.get('errorMessage') or response.get('CustomerMessage') or 'STK Push rejected.')
        return response

    def stk_query(self, *, checkout_request_id: str) -> dict:
        timestamp, password = self._timestamp_and_password()
        payload = {
            'BusinessShortCode': self.config.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id,
        }
        request = Request(
            f'{self.config.base_url}/mpesa/stkpushquery/v1/query',
            data=json.dumps(payload).encode(),
            method='POST',
            headers={
                'Authorization': f'Bearer {self.access_token()}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        response = self._request(request)
        if 'ResultCode' not in response:
            raise DarajaError(response.get('errorMessage') or 'Daraja STK query did not return a final result.')
        return response

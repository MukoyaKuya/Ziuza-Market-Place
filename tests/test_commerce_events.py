import json
import logging

import pytest

from apps.core.commerce_events import emit_commerce_event


def test_commerce_event_has_stable_versioned_shape(caplog):
    with caplog.at_level(logging.INFO, logger='commerce'):
        emit_commerce_event('payment.confirmed', payment_id='payment-1', amount='100.00', currency='KES')

    payload = json.loads(caplog.records[-1].message)
    assert payload['event'] == 'payment.confirmed'
    assert payload['version'] == 1
    assert payload['payment_id'] == 'payment-1'
    assert payload['timestamp']


@pytest.mark.parametrize('field', ['address', 'email', 'payload', 'phone', 'secret', 'token'])
def test_commerce_event_rejects_sensitive_fields(field):
    with pytest.raises(ValueError, match='sensitive'):
        emit_commerce_event('unsafe.event', **{field: 'private'})

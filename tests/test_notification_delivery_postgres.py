import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from apps.marketplace.notifications.delivery import deliver_pending_notifications
from apps.marketplace.notifications.models import DeliveryStatus, NotificationDelivery, notify

User = get_user_model()


@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-level locking')
@pytest.mark.django_db(transaction=True)
def test_two_delivery_workers_claim_immediate_notification_once(monkeypatch):
    recipient = User.objects.create_user(email='delivery-race@ziuza.co.ke', password='Password123!')
    notification = notify(recipient=recipient, type='order_placed', title='One delivery')
    sends = []
    barrier = threading.Barrier(2)

    def record_send(deliveries):
        sends.append([delivery.id for delivery in deliveries])
        return 1

    monkeypatch.setattr('apps.marketplace.notifications.delivery._send_group', record_send)

    def run_worker():
        barrier.wait()
        try:
            connection.ensure_connection()
            deliver_pending_notifications()
        finally:
            connection.close()

    workers = [threading.Thread(target=run_worker) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    delivery = NotificationDelivery.objects.get(notification=notification)
    assert delivery.status == DeliveryStatus.SENT
    assert delivery.attempts == 1
    assert len(sends) == 1

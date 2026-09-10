from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.marketplace.payments.daraja import DarajaError
from apps.marketplace.payments.models import Payment
from apps.marketplace.payments.providers import MpesaPaymentProvider


class Command(BaseCommand):
    help = 'Query Daraja and reconcile one pending or ambiguous M-Pesa payment.'

    def add_arguments(self, parser):
        parser.add_argument('--payment', required=True, dest='payment_id')
        parser.add_argument('--checkout-id', default='', dest='checkout_id')

    def handle(self, *args, **options):
        try:
            payment = Payment.objects.select_related('order').get(pk=options['payment_id'])
            payment = MpesaPaymentProvider().reconcile_payment(
                payment=payment,
                checkout_request_id=options['checkout_id'],
            )
        except (Payment.DoesNotExist, ValidationError, DarajaError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f'Reconciled {payment.provider_reference}: payment={payment.status}, order={payment.order.payment_status}.'
        ))

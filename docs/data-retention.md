# Data Retention

Ziuza separates operational cleanup from legally significant marketplace records.

## Automated Operational Cleanup

`python manage.py purge_operational_data` is report-only. Review its counts, then use
`python manage.py purge_operational_data --execute`. Celery Beat runs the execute mode weekly.

Default windows are configurable through:

| Setting | Default | Data |
|---|---:|---|
| `RETENTION_OTP_DAYS` | 1 day | Expired or consumed email OTPs |
| `RETENTION_RECENT_VIEWS_DAYS` | 180 days | Buyer listing-view history |
| `RETENTION_DELIVERY_DAYS` | 90 days | Completed email delivery queue rows |
| `RETENTION_READ_NOTIFICATION_DAYS` | 180 days | Read in-app notifications |
| `RETENTION_CALLBACK_PAYLOAD_DAYS` | 365 days | Raw callback payloads; event metadata remains |

Expired Django sessions are also removed. The command never deletes orders, payments,
messages, disputes, reviews, seller verification records, or callback audit events.
Rotating `SECRET_KEY` invalidates outstanding keyed OTPs; users can request a new code.

## Legal Policy Required

Before launch, the marketplace operator must approve retention periods for orders,
payment records, tax records, buyer-protection evidence, seller identity records,
messages, backups, and account-erasure requests. Those periods depend on Kenyan tax,
consumer-protection, payment, and privacy obligations and are intentionally not guessed
in application code.

Account closure should pseudonymize personal profile data while preserving financial and
dispute records. It must not use cascading `User.delete()` because protected marketplace
records are intentionally retained.

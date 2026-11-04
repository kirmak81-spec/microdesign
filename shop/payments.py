"""Robokassa adapter. No payment confirmation through browser redirects."""

import hashlib, hmac
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from django.conf import settings


def digest(value):
    if settings.ROBOKASSA_HASH not in {"md5", "sha256", "sha512"}:
        raise ValueError("Unsupported Robokassa hash")
    return hashlib.new(settings.ROBOKASSA_HASH, value.encode()).hexdigest()


def payment_url(order):
    if not settings.PAYMENTS_ENABLED or not all(
        [
            settings.ROBOKASSA_LOGIN,
            settings.ROBOKASSA_PASSWORD1,
            settings.ROBOKASSA_PASSWORD2,
        ]
    ):
        return None
    if order.status != "ready" or order.shipping_cost is None:
        return None
    amount = f"{order.total:.2f}"
    signature = digest(
        f"{settings.ROBOKASSA_LOGIN}:{amount}:{order.pk}:{settings.ROBOKASSA_PASSWORD1}"
    )
    return "https://auth.robokassa.ru/Merchant/Index.aspx?" + urlencode(
        {
            "MerchantLogin": settings.ROBOKASSA_LOGIN,
            "OutSum": amount,
            "InvId": order.pk,
            "Description": str(order),
            "SignatureValue": signature,
            "Culture": "ru",
            "IsTest": int(settings.ROBOKASSA_TEST),
            "Email": order.email,
        }
    )


def valid_result(data, order):
    if not settings.PAYMENTS_ENABLED or not settings.ROBOKASSA_PASSWORD2:
        return False
    if any(k.lower().startswith("shp_") for k in data):
        return False
    amount, invoice = data.get("OutSum", ""), data.get("InvId", "")
    try:
        received = Decimal(amount)
        if (
            not received.is_finite()
            or received != order.total
            or int(invoice) != order.pk
        ):
            return False
    except (InvalidOperation, ValueError, TypeError):
        return False
    if (
        order.status != "ready" and order.paid_at is None
    ) or order.shipping_cost is None:
        return False
    signature = digest(f"{amount}:{invoice}:{settings.ROBOKASSA_PASSWORD2}")
    return hmac.compare_digest(signature, data.get("SignatureValue", "").lower())

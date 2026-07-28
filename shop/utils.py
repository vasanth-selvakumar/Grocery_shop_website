# shop/utils.py

from django.core.mail import send_mail
from django.conf import settings


def send_order_notification(order):
    total_price = order.product.price * order.quantity

    subject = '🛒 New Order Received!'
    message = (
        f"New Order!\n"
        f"Customer: {order.customer.get_full_name() or order.customer.username}\n"
        f"Mobile: {order.customer.mobile_number}\n"
        f"Product: {order.product.name} (Qty: {order.quantity})\n"
        f"Price: ₹{order.product.price} x {order.quantity} = ₹{total_price}\n"
        f"Address: {order.address}"
    )

    send_mail(
        subject,
        message,
        None,
        [settings.EMAIL_HOST_USER],
        fail_silently=False,
    )


def send_delivery_otp(order):
    subject = 'Your order is out for delivery!'
    message = (
        f"Hi {order.customer.first_name},\n\n"
        f"Your order for {order.product.name} is out for delivery!\n"
        f"Share this OTP with the delivery person to confirm delivery: {order.delivery_otp}"
    )
    send_mail(
        subject,
        message,
        None,
        [order.customer.email],
        fail_silently=False,
    )


def send_delivery_email(order):
    subject = 'Your order has been delivered!'
    message = f"""Hi {order.customer.first_name},

Your order for {order.product.name} (Qty: {order.quantity}) has been delivered successfully.

Thank you for shopping with Vasanth Store!
"""
    send_mail(
        subject,
        message,
        None,
        [order.customer.email],
        fail_silently=False,
    )
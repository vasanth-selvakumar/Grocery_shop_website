# shop/utils.py

import requests
from django.core.mail import send_mail
from django.conf import settings
from .models import Cart


def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart


def send_order_notification(order):
    total_price = order.product.price * order.quantity

    subject = '🛒 New Order Received!'
    message = (
        f"New Order!\n"
        f"Customer: {order.customer.get_full_name() or order.customer.username}\n"
        f"Phone: {order.customer.mobile_number}\n"
        f"Product: {order.product.name} (Qty: {order.quantity})\n"
        f"Price: ₹{order.product.price} x {order.quantity} = ₹{total_price}\n"
        f"Payment Method: {order.get_payment_method_display()}\n"
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
    print(f"Sending OTP to: {order.customer.email}")   # <-- idha add pannunga
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

def send_order_email_notification(orders):
    first_order = orders[0]
    total_amount = sum(o.product.price * o.quantity for o in orders) + first_order.delivery_charge

    items_text = "\n".join(
        f"- {o.product.name} — Qty: {o.quantity} — ₹{o.product.price * o.quantity}"
        for o in orders
    )

    subject = '🛒 New Order Received!'
    message = (
        f"New Order!\n"
        f"Customer: {first_order.customer.get_full_name() or first_order.customer.username}\n"
        f"Phone: {first_order.customer.mobile_number}\n"
        f"Address: {first_order.address}\n"
        f"Payment Method: {first_order.get_payment_method_display()}\n\n"
        f"Items ordered:\n{items_text}\n\n"
        f"Total (incl. delivery ₹{first_order.delivery_charge}): ₹{total_amount}"
    )

    send_mail(
        subject,
        message,
        None,
        [settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
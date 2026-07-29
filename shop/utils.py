import requests
from django.conf import settings

def send_order_email_notification(order):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json"
    }
    data = {
        "sender": {"name": "Vasanth Store", "email": "selvakumarvasanth80@gmail.com"},
        "to": [{"email": "OWNER_EMAIL_HERE@gmail.com"}],
        "subject": "New Order Received",
        "htmlContent": f"""
            <p>New order received:</p>
            <ul>
                <li>Customer: {order.customer.get_full_name() or order.customer.username}</li>
                <li>Product: {order.product.name}</li>
                <li>Quantity: {order.quantity}</li>
                <li>Address: {order.address}</li>
                <li>Payment: {order.get_payment_method_display()}</li>
                <li>Delivery charge: ₹{order.delivery_charge}</li>
            </ul>
        """
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        return response.status_code
    except Exception as e:
        print(f"Email send failed: {e}")# shop/utils.py

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
# shop/utils.py

from twilio.rest import Client
from django.conf import settings

def send_order_notification(order):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    total_price = order.product.price * order.quantity

    message_body = (
        f"🛒 New Order!\n"
        f"Customer: {order.customer.get_full_name() or order.customer.username}\n"
        f"Mobile: {order.customer.mobile_number}\n"
        f"Product: {order.product.name} (Qty: {order.quantity})\n"
        f"Price: ₹{order.product.price} x {order.quantity} = ₹{total_price}\n"
        f"Address: {order.address}"
    )

    client.messages.create(
        body=message_body,
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=settings.SHOP_OWNER_WHATSAPP_NUMBER
    )

def send_delivery_otp(order):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message_body = (
        f"📦 Your order for {order.product.name} is out for delivery!\n"
        f"Share this OTP with the delivery person to confirm delivery: {order.delivery_otp}"
    )
    client.messages.create(
        body=message_body,
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=f'whatsapp:+91{order.customer.mobile_number}'
    )    
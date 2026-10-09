from django import template

from ..utils import get_or_create_cart

register = template.Library()


@register.simple_tag(takes_context=True)
def cart_count(context):
    request = context.get('request')
    if request is None:
        return 0
    try:
        cart = get_or_create_cart(request)
        return sum(item.quantity for item in cart.items.all())
    except Exception:
        return 0
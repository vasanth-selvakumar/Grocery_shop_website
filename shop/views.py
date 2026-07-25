from django.views.generic import ListView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product, Order
from .utils import send_order_notification


class ProductListView(ListView):
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'


@login_required
def place_order(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity'))
        address = request.POST.get('address')

        order = Order.objects.create(
            customer=request.user,
            product=product,
            quantity=quantity,
            address=address,
        )
        send_order_notification(order)
        return redirect('order_success')

    return render(request, 'place_order.html', {'product': product})


def order_success(request):
    return render(request, 'order_success.html')

from django.contrib.auth import login
from .forms import CustomerSignUpForm

def signup_view(request):
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('product_list')
    else:
        form = CustomerSignUpForm()
    return render(request, 'signup.html', {'form': form})

def verify_delivery(request):
    message = ''
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        otp = request.POST.get('otp')
        try:
            order = Order.objects.get(id=order_id, status='out_for_delivery')
            if order.delivery_otp == otp:
                order.status = 'delivered'
                order.delivery_otp = ''
                order.save()
                message = '✅ Delivery confirmed successfully!'
            else:
                message = '❌ Incorrect OTP. Try again.'
        except Order.DoesNotExist:
            message = '❌ Invalid Order ID or order not out for delivery.'

    return render(request, 'verify_delivery.html', {'message': message})    
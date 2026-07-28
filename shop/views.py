from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Product, Cart, CartItem, Order, Category
from .utils import send_order_notification, send_delivery_otp, send_delivery_email


def home(request):
    return render(request, 'home.html')

class ProductListView(ListView):
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__name__iexact=category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_category'] = self.request.GET.get('category', '')
        return context


@login_required
def place_order(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity'))
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method')
        screenshot = request.FILES.get('payment_screenshot')

        if payment_method == 'upi' and not screenshot:
            return render(request, 'place_order.html', {
                'product': product,
                'error': 'UPI screenshot compulsory'
            })

        order = Order.objects.create(
            customer=request.user,
            product=product,
            quantity=quantity,
            address=address,
            payment_method=payment_method,
            payment_screenshot=screenshot if payment_method == 'upi' else None
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
        action = request.POST.get('action')

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            order = None
            message = '❌ Invalid Order ID.'

        if order:
            if action == 'send_otp':
                order.generate_otp()
                send_delivery_otp(order)
                message = f'✅ OTP sent to customer email for Order #{order_id}'

            elif action == 'verify':
                otp = request.POST.get('otp')
                if order.delivery_otp == otp:
                    order.status = 'delivered'
                    order.delivery_otp = ''
                    order.save()
                    send_delivery_email(order)
                    message = '✅ Delivery confirmed successfully!'
                else:
                    message = '❌ Incorrect OTP. Try again.'

    return render(request, 'verify_delivery.html', {'message': message})

@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    if not cart.items.exists():
        return redirect('view_cart')

    if request.method == 'POST':
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method')
        screenshot = request.FILES.get('payment_screenshot')

        if payment_method == 'upi' and not screenshot:
            return render(request, 'checkout.html', {
                'cart': cart,
                'error': 'UPI screenshot compulsory'
            })

        for item in cart.items.all():
            order = Order.objects.create(
                customer=request.user,
                product=item.product,
                quantity=item.quantity,
                address=address,
                status='pending',
                payment_method=payment_method,
                payment_screenshot=screenshot if payment_method == 'upi' else None
            )
            send__order_notification(order)
        cart.items.all().delete()
        return render(request, 'order_success.html')

    return render(request, 'checkout.html', {'cart': cart})   

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Product, Cart, CartItem, Order
from .utils import send_order_notification


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()
    return redirect('view_cart')


@login_required
def view_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart.html', {'cart': cart})


@login_required
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    action = request.POST.get('action')
    if action == 'increase':
        item.quantity += 1
        item.save()
    elif action == 'decrease':
        item.quantity -= 1
        if item.quantity <= 0:
            item.delete()
        else:
            item.save()
    elif action == 'remove':
        item.delete()
    return redirect('view_cart')


@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    if not cart.items.exists():
        return redirect('view_cart')

    if request.method == 'POST':
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method')
        screenshot = request.FILES.get('payment_screenshot')

        if payment_method == 'upi' and not screenshot:
            return render(request, 'checkout.html', {
                'cart': cart,
                'error': 'UPI screenshot compulsory'
            })

        for item in cart.items.all():
            order = Order.objects.create(
                customer=request.user,
                product=item.product,
                quantity=item.quantity,
                address=address,
                status='pending',
                payment_method=payment_method,
                payment_screenshot=screenshot if payment_method == 'upi' else None
            )
            send_order_notification(order)
        cart.items.all().delete()
        return render(request, 'order_success.html')

    return render(request, 'checkout.html', {'cart': cart})    

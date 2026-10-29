import calendar
import re
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import (
    Case, When, F, IntegerField, Q, Sum, Count, DecimalField, ExpressionWrapper,
)
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect, render
from .models import Product, Cart, CartItem, Order, Category, Address, DELIVERY_SLOTS
from .forms import CustomerSignUpForm
from .utils import (
    send_order_notification,
    send_delivery_otp,
    send_delivery_email,
    send_order_email_notification,
    get_or_create_cart,
)

# Delivery rule: idha inga maathikkalaam
FREE_DELIVERY_ABOVE = 299
DELIVERY_CHARGE = 20

# Slot mudiyaradhukku ethana manineram munnadi booking close aagum (1 = 1 hour munnadi)
SLOT_CLOSE_BEFORE_HOURS = 1

# Home page "Popular products" la ovvoru category la irundhum ethana products kaattanum
POPULAR_PER_CATEGORY = 2

# Thermal bill la varra shop details
SHOP_NAME = 'Vasanth Store'
SHOP_ADDRESS = 'Sittilarai'
SHOP_PHONE = '8015180625'

# Home page category icons: pudhu category vandha inga oru line add pannunga
CATEGORY_ICONS = {
    'Snacks': '🍿',
    'Groceries': '🛒',
    'Juices': '🧃',
    'Stationery': '✏️',
    'Oil': '🫒',
    'Chocolates': '🍫',
    'Masala Items': '🌶️',
    'Sanitary Pads': '🧻',
    'Soap and Powder': '🧼',
}
DEFAULT_CATEGORY_ICON = '📦'


def get_cart_total(cart):
    """cart.total_price method ah irundhaalum property ah irundhaalum work aagum."""
    total = cart.total_price
    return total() if callable(total) else total


def get_delivery_info(subtotal):
    """subtotal kudutha, delivery charge / total / free delivery ku innum evlo venum nu solludhu."""
    if subtotal >= FREE_DELIVERY_ABOVE:
        charge = 0
        more_needed = 0
    else:
        charge = DELIVERY_CHARGE
        more_needed = FREE_DELIVERY_ABOVE - subtotal
    return {
        'subtotal': subtotal,
        'delivery_charge': charge,
        'total': subtotal + charge,
        'more_needed': more_needed,
        'free_above': FREE_DELIVERY_ABOVE,
        'progress': min(100, int(subtotal * 100 / FREE_DELIVERY_ABOVE)) if subtotal > 0 else 0,
    }


def get_total_savings(items):
    """Sum of (MRP - price) x quantity for items that have an MRP."""
    savings = 0
    for item in items:
        mrp = item.product.mrp
        if mrp and mrp > item.product.price:
            savings += (mrp - item.product.price) * item.quantity
    return savings


# ---------------- Delivery slot helpers ----------------

def _slot_open_today(end_hour, now):
    """Indha slot innaiku innum book panna mudiyumaa?"""
    current = now.hour + now.minute / 60
    return current < end_hour - SLOT_CLOSE_BEFORE_HOURS


def get_slot_info(selected_day='', selected_slot=''):
    """Templates ku slot options. Today la neram dhaandina slots 'today_ok = False' aagum."""
    now = timezone.localtime()
    today = now.date()

    slots = [
        {'key': key, 'label': label, 'today_ok': _slot_open_today(end, now)}
        for key, label, start, end in DELIVERY_SLOTS
    ]
    today_open = any(s['today_ok'] for s in slots)

    if selected_day not in ('today', 'tomorrow'):
        selected_day = 'today' if today_open else 'tomorrow'

    return {
        'today_date': today,
        'tomorrow_date': today + timedelta(days=1),
        'slots': slots,
        'today_open': today_open,
        'selected_day': selected_day,
        'selected_slot': selected_slot,
    }


def parse_delivery_slot(request):
    """POST la irundhu (delivery_date, slot_key, error) edukkum."""
    day = request.POST.get('delivery_day', '')
    slot_key = request.POST.get('delivery_slot', '')

    now = timezone.localtime()
    today = now.date()

    if day == 'today':
        chosen = today
    elif day == 'tomorrow':
        chosen = today + timedelta(days=1)
    else:
        return None, None, 'Please select a delivery slot.'

    ends = {key: end for key, label, start, end in DELIVERY_SLOTS}
    if slot_key not in ends:
        return None, None, 'Please select a delivery slot.'

    if chosen == today and not _slot_open_today(ends[slot_key], now):
        return None, None, 'That slot is no longer available for today. Please choose another slot.'

    return chosen, slot_key, ''


def get_cart_qty(request):
    """{product_id: quantity} for the current cart, plus total item count."""
    cart = get_or_create_cart(request)
    qty_map = {item.product_id: item.quantity for item in cart.items.all()}
    return qty_map, sum(qty_map.values())


def home(request):
    # Best Offers: MRP irukkura, stock irukkura products, athigama % off mudhala
    offers = list(Product.objects.filter(mrp__isnull=False, mrp__gt=F('price'), stock_quantity__gt=0))
    offers.sort(key=lambda p: p.discount_percent, reverse=True)
    offers = offers[:8]

    # Category icons: CATEGORY_ICONS (mela top la irukku) la irundhu varum
    order = ['Snacks', 'Groceries', 'Juices', 'Stationery', 'Oil']
    names = set(Product.objects.values_list('category', flat=True))
    names = sorted(names, key=lambda n: (order.index(n) if n in order else len(order), n))
    categories = [
        {'name': n, 'icon': CATEGORY_ICONS.get(n, DEFAULT_CATEGORY_ICON)}
        for n in names
    ]

    # Popular products: ovvoru category la irundhum latest in-stock products (POPULAR_PER_CATEGORY),
    # row la kalandhu varum (Snacks, Groceries, Juices, Stationery, Oil, thirumba Snacks...)
    by_category = {}
    for p in Product.objects.filter(stock_quantity__gt=0).order_by('-id'):
        group = by_category.setdefault(p.category, [])
        if len(group) < POPULAR_PER_CATEGORY:
            group.append(p)

    category_order = [n for n in names if n in by_category]
    new_products = []
    for i in range(POPULAR_PER_CATEGORY):
        for n in category_order:
            if i < len(by_category[n]):
                new_products.append(by_category[n][i])

    cart_qty, cart_count = get_cart_qty(request)

    return render(request, 'home.html', {
        'offers': offers,
        'categories': categories,
        'new_products': new_products,
        'cart_qty': cart_qty,
        'cart_count': cart_count,
    })


class ProductListView(ListView):
    model = Product
    template_name = 'product_list.html'
    context_object_name = 'products'

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__iexact=category)
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | Q(category__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_category'] = self.request.GET.get('category', '')
        context['q'] = self.request.GET.get('q', '')

        cart_qty, cart_count = get_cart_qty(self.request)
        context['cart_qty'] = cart_qty
        context['cart_count'] = cart_count

        # Sidebar: each category with its products
        groups = {}
        for p in Product.objects.order_by('name'):
            groups.setdefault(p.category, []).append(p)

        order = ['Snacks', 'Groceries', 'Juices', 'Stationery', 'Oil']
        context['category_groups'] = [
            {'name': name, 'products': prods}
            for name, prods in sorted(
                groups.items(),
                key=lambda kv: (order.index(kv[0]) if kv[0] in order else len(order), kv[0])
            )
        ]
        return context


@require_POST
def cart_ajax(request, product_id):
    """Blinkit-style ADD / + / - without page reload. Returns JSON."""
    product = get_object_or_404(Product, id=product_id)
    cart = get_or_create_cart(request)
    action = request.POST.get('action', 'add')

    item = CartItem.objects.filter(cart=cart, product=product).first()
    qty = item.quantity if item else 0
    error = ''

    if action in ('add', 'increase'):
        if qty + 1 > product.stock_quantity:
            error = f'Only {product.stock_quantity} left in stock.'
        else:
            if item:
                item.quantity += 1
                item.save()
            else:
                item = CartItem.objects.create(cart=cart, product=product, quantity=1)
            qty = item.quantity

    elif action == 'decrease':
        if item:
            item.quantity -= 1
            if item.quantity <= 0:
                item.delete()
                qty = 0
            else:
                item.save()
                qty = item.quantity

    _, cart_count = get_cart_qty(request)

    return JsonResponse({
        'ok': not error,
        'error': error,
        'qty': qty,
        'cart_count': cart_count,
    })


@login_required
def place_order(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    addresses = request.user.addresses.all()

    def page(**extra):
        context = {
            'product': product,
            'addresses': addresses,
            'slot_info': get_slot_info(
                request.POST.get('delivery_day', ''),
                request.POST.get('delivery_slot', ''),
            ),
            'free_above': FREE_DELIVERY_ABOVE,
            'delivery_fee': DELIVERY_CHARGE,
        }
        context.update(extra)
        return render(request, 'place_order.html', context)

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 1
        if quantity < 1:
            quantity = 1

        # Address: saved select pannirukkaanga, illa pudhusa type pannirukkaanga
        choice = request.POST.get('address_choice', 'new')
        save_new = False
        label = 'Home'

        if choice != 'new' and choice.isdigit():
            saved = get_object_or_404(Address, id=int(choice), user=request.user)
            address = saved.address
        else:
            address = request.POST.get('address', '').strip()
            save_new = request.POST.get('save_address') == 'on'
            label = request.POST.get('label', '').strip() or 'Home'

        if not address:
            return page(error='Please enter a delivery address.')

        delivery_date, delivery_slot, slot_error = parse_delivery_slot(request)
        if slot_error:
            return page(error=slot_error)

        if quantity > product.stock_quantity:
            return page(error=f'Only {product.stock_quantity} left in stock.')

        info = get_delivery_info(product.price * quantity)

        with transaction.atomic():
            order = Order.objects.create(
                customer=request.user,
                product=product,
                quantity=quantity,
                address=address,
                payment_method='cod',
                delivery_charge=info['delivery_charge'],
                delivery_date=delivery_date,
                delivery_slot=delivery_slot,
            )
            product.stock_quantity -= quantity
            product.save()

            if save_new and not Address.objects.filter(user=request.user, address=address).exists():
                Address.objects.create(user=request.user, label=label[:30], address=address)

        send_order_notification(order)
        try:
            send_order_email_notification(order)
        except Exception as e:
            print(f"Email notification failed: {e}")

        # Success page ku indha order ah session la vachikkirom
        request.session['last_order_ids'] = [order.id]
        return redirect('order_success')

    return page()


def order_success(request):
    """Order potta aprm varra page. Session la irukkura last orders ah kaattum."""
    order_ids = request.session.get('last_order_ids', [])
    orders = []
    delivery_slot_text = ''

    if order_ids and request.user.is_authenticated:
        orders = list(
            Order.objects.filter(id__in=order_ids, customer=request.user)
            .select_related('product')
            .order_by('id')
        )
        for o in orders:
            o.line_total = o.product.price * o.quantity
        if orders:
            delivery_slot_text = orders[0].delivery_slot_text

    return render(request, 'order_success.html', {
        'orders': orders,
        'delivery_slot_text': delivery_slot_text,
    })


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


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_or_create_cart(request)

    quantity = int(request.POST.get('quantity', 1))
    if quantity < 1:
        quantity = 1

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    return redirect('view_cart')


def add_selected_to_cart(request):
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_products')

        if not selected_ids:
            return redirect('product_list')

        cart = get_or_create_cart(request)

        for product_id in selected_ids:
            product = get_object_or_404(Product, id=product_id)
            item, created = CartItem.objects.get_or_create(cart=cart, product=product)
            if not created:
                item.quantity += 1
                item.save()

        return redirect('view_cart')

    return redirect('product_list')


def view_cart(request):
    cart = get_or_create_cart(request)
    context = {'cart': cart}
    context.update(get_delivery_info(get_cart_total(cart)))
    return render(request, 'cart.html', context)


def update_cart_item(request, item_id):
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
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
@require_POST
def buy_again(request, order_id):
    """My Orders la irundhu: andha order la vaangina product + quantity ah cart la add pannum."""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    product = order.product

    if product.stock_quantity <= 0:
        return redirect('my_orders')

    cart = get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={'quantity': 0}
    )
    # stock ku mela poga koodaadhu
    item.quantity = min(item.quantity + order.quantity, product.stock_quantity)
    item.save()
    return redirect('view_cart')


def checkout_context(request, cart, **extra):
    context = {
        'cart': cart,
        'addresses': request.user.addresses.all(),
        'slot_info': get_slot_info(
            request.POST.get('delivery_day', ''),
            request.POST.get('delivery_slot', ''),
        ),
    }
    context.update(get_delivery_info(get_cart_total(cart)))
    context['total_savings'] = get_total_savings(cart.items.all())
    context.update(extra)
    return context


@login_required
def checkout(request):
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        return redirect('view_cart')

    if request.method == 'POST':
        # Address: saved address select pannirukkaanga, illa pudhusa type pannirukkaanga
        choice = request.POST.get('address_choice', 'new')
        save_new = False
        label = 'Home'

        if choice != 'new' and choice.isdigit():
            saved = get_object_or_404(Address, id=int(choice), user=request.user)
            address = saved.address
        else:
            address = request.POST.get('address', '').strip()
            save_new = request.POST.get('save_address') == 'on'
            label = request.POST.get('label', '').strip() or 'Home'

        if not address:
            return render(request, 'checkout.html', checkout_context(
                request, cart, error='Please enter a delivery address.'
            ))

        delivery_date, delivery_slot, slot_error = parse_delivery_slot(request)
        if slot_error:
            return render(request, 'checkout.html', checkout_context(
                request, cart, error=slot_error
            ))

        # Stock illana order aagaadhu
        for item in cart.items.all():
            if item.quantity > item.product.stock_quantity:
                return render(request, 'checkout.html', checkout_context(
                    request, cart,
                    error=f'{item.product.name}: only {item.product.stock_quantity} left in stock.'
                ))

        delivery_charge = get_delivery_info(get_cart_total(cart))['delivery_charge']

        orders = []
        with transaction.atomic():
            for index, item in enumerate(cart.items.all()):
                order = Order.objects.create(
                    customer=request.user,
                    product=item.product,
                    quantity=item.quantity,
                    address=address,
                    status='pending',
                    payment_method='cod',
                    # oru checkout ku ore delivery charge (first order la mattum)
                    delivery_charge=delivery_charge if index == 0 else 0,
                    delivery_date=delivery_date,
                    delivery_slot=delivery_slot,
                )
                orders.append(order)

                # 500 la 10 vanguna 490 aagum
                item.product.stock_quantity -= item.quantity
                item.product.save()

            # Pudhu address ah save pannu (same address already irundha thirumba save panna vendaam)
            if save_new and not Address.objects.filter(user=request.user, address=address).exists():
                Address.objects.create(user=request.user, label=label[:30], address=address)

        try:
            send_order_email_notification(orders)
        except Exception as e:
            print(f"Email notification failed: {e}")

        cart.items.all().delete()

        # Success page ku indha orders ah session la vachikkirom
        request.session['last_order_ids'] = [o.id for o in orders]
        # render ku bathila redirect: refresh pannaa order thirumba pogaadhu
        return redirect('order_success')

    return render(request, 'checkout.html', checkout_context(request, cart))


def is_owner(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_owner)
def owner_dashboard(request):
    message = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            order = None
            message = '❌ Invalid Order ID.'
        if order:
            if action == 'update_status':
                new_status = request.POST.get('status')
                order.status = new_status
                order.save()
                if new_status == 'out_for_delivery':
                    order.generate_otp()
                    send_delivery_otp(order)
                    message = f'✅ Status updated & OTP sent for Order #{order.id}'
                else:
                    message = f'✅ Status updated to {new_status} for Order #{order.id}'
            elif action == 'verify_otp':
                otp = request.POST.get('otp')
                if order.delivery_otp == otp:
                    order.status = 'delivered'
                    order.delivery_otp = ''
                    order.save()
                    send_delivery_email(order)
                    message = f'✅ Order #{order.id} marked as delivered!'
                else:
                    message = '❌ Incorrect OTP. Try again.'

    # Delivery date + slot padi sort: inniki morning -> afternoon -> evening, appuram naalaiku.
    # Slot illatha pazhaya orders kadaisila varum.
    orders = (
        Order.objects.exclude(status__in=['delivered', 'cancelled'])
        .annotate(
            slot_order=Case(
                When(delivery_slot='morning', then=0),
                When(delivery_slot='afternoon', then=1),
                When(delivery_slot='evening', then=2),
                default=3,
                output_field=IntegerField(),
            )
        )
        .order_by(F('delivery_date').asc(nulls_last=True), 'slot_order', '-created_at')
    )

    return render(request, 'owner_dashboard.html', {
        'orders': orders,
        'message': message,
    })


@login_required
@user_passes_test(is_owner)
def stock_dashboard(request):
    """Product Stock page: out of stock first, then low stock (stock <= min_stock), then the rest."""
    products = Product.objects.annotate(
        priority=Case(
            When(stock_quantity=0, then=0),
            When(stock_quantity__lte=F('min_stock'), then=1),
            default=2,
            output_field=IntegerField(),
        )
    ).order_by('priority', 'stock_quantity', 'name')

    return render(request, 'stock_dashboard.html', {
        'products': products,
    })


@login_required
@user_passes_test(is_owner)
def print_bill(request, order_id):
    """80mm thermal bill. Same customer + same address + ore checkout (±60 sec) la irukkura ellaa items um ore bill la varum."""
    order = get_object_or_404(Order.objects.select_related('customer', 'product'), id=order_id)

    window = timedelta(seconds=60)
    related = (
        Order.objects.filter(
            customer=order.customer,
            address=order.address,
            created_at__gte=order.created_at - window,
            created_at__lte=order.created_at + window,
        )
        .filter(~Q(status='cancelled') | Q(id=order.id))
        .select_related('product')
        .order_by('id')
    )

    lines = []
    subtotal = 0
    delivery = 0
    for o in related:
        amount = o.product.price * o.quantity
        subtotal += amount
        delivery += o.delivery_charge or 0
        lines.append({
            'name': o.product.name,
            'qty': o.quantity,
            'price': o.product.price,
            'amount': amount,
        })

    customer = order.customer
    customer_name = customer.get_full_name() or customer.username
    customer_mobile = getattr(customer, 'mobile_number', '') or ''

    return render(request, 'bill.html', {
        'shop_name': SHOP_NAME,
        'shop_address': SHOP_ADDRESS,
        'shop_phone': SHOP_PHONE,
        'order_ids': [o.id for o in related],
        'created_at': timezone.localtime(order.created_at),
        'customer_name': customer_name,
        'customer_mobile': customer_mobile,
        'address': order.address,
        'delivery_slot': order.delivery_slot_text,
        'payment': order.get_payment_method_display(),
        'lines': lines,
        'subtotal': subtotal,
        'delivery': delivery,
        'total': subtotal + delivery,
    })


@login_required
@user_passes_test(is_owner)
def sales_report(request):
    """Delivered orders mattum. ?date=YYYY-MM-DD (oru naal), ?month=YYYY-MM (oru maasam)."""
    tz = timezone.get_current_timezone()
    today = timezone.localtime().date()

    def day_range(d):
        start = timezone.make_aware(datetime.combine(d, datetime.min.time()), tz)
        return start, start + timedelta(days=1)

    # --- Selected day / month ---
    sel_day = None
    try:
        sel_day = date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        pass

    if sel_day is None:
        try:
            y, m = map(int, request.GET.get('month', '').split('-'))
            first = date(y, m, 1)
            sel_day = today if (first.year, first.month) == (today.year, today.month) else first
        except ValueError:
            sel_day = today

    month_first = sel_day.replace(day=1)
    last_day_num = calendar.monthrange(month_first.year, month_first.month)[1]
    month_last = month_first.replace(day=last_day_num)
    week_first = sel_day - timedelta(days=sel_day.weekday())  # Monday

    line_total = ExpressionWrapper(
        F('quantity') * F('product__price'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    delivered = Order.objects.filter(status='delivered')

    def summary(d_from, d_to_exclusive):
        start = day_range(d_from)[0]
        end = day_range(d_to_exclusive)[0]
        qs = delivered.filter(created_at__gte=start, created_at__lt=end)
        items = qs.aggregate(t=Sum(line_total))['t'] or 0
        delivery = qs.aggregate(t=Sum('delivery_charge'))['t'] or 0
        return {'orders': qs.count(), 'sales': items + delivery}

    day_summary = summary(sel_day, sel_day + timedelta(days=1))
    week_summary = summary(week_first, week_first + timedelta(days=7))
    month_summary = summary(month_first, month_last + timedelta(days=1))

    # --- Selected day orders ---
    ds, de = day_range(sel_day)
    day_orders = []
    for o in (delivered.filter(created_at__gte=ds, created_at__lt=de)
              .select_related('customer', 'product').order_by('created_at')):
        amount = o.product.price * o.quantity
        day_orders.append({
            'id': o.id,
            'time': timezone.localtime(o.created_at),
            'customer': o.customer.get_full_name() or o.customer.username,
            'product': o.product.name,
            'qty': o.quantity,
            'payment': o.get_payment_method_display(),
            'amount': amount + (o.delivery_charge or 0),
        })

    # --- Selected month: ella naal um ---
    m_start = day_range(month_first)[0]
    m_end = day_range(month_last)[1]
    rows = (
        delivered.filter(created_at__gte=m_start, created_at__lt=m_end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(orders=Count('id'), items=Sum(line_total), delivery=Sum('delivery_charge'))
    )
    by_day = {r['day']: r for r in rows}

    month_days = []
    last_to_show = min(month_last, today)
    d = month_first
    while d <= last_to_show:
        r = by_day.get(d)
        sales = ((r['items'] or 0) + (r['delivery'] or 0)) if r else 0
        month_days.append({'date': d, 'orders': r['orders'] if r else 0, 'sales': sales})
        d += timedelta(days=1)

    max_daily = max([x['sales'] for x in month_days] + [1])
    for x in month_days:
        x['pct'] = int(x['sales'] * 100 / max_daily) if x['sales'] else 0

    top_products = (
        delivered.filter(created_at__gte=m_start, created_at__lt=m_end)
        .values('product__name')
        .annotate(qty=Sum('quantity'), revenue=Sum(line_total))
        .order_by('-qty')[:10]
    )

    # Month select: last 12 months
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append({
            'value': f'{y}-{m:02d}',
            'label': date(y, m, 1).strftime('%B %Y'),
        })
        m -= 1
        if m == 0:
            m, y = 12, y - 1

    return render(request, 'sales_report.html', {
        'sel_day': sel_day,
        'prev_day': sel_day - timedelta(days=1),
        'next_day': sel_day + timedelta(days=1) if sel_day < today else None,
        'today': today,
        'month_value': f'{month_first.year}-{month_first.month:02d}',
        'month_label': month_first.strftime('%B %Y'),
        'months': months,
        'day_summary': day_summary,
        'week_summary': week_summary,
        'month_summary': month_summary,
        'day_orders': day_orders,
        'month_days': month_days,
        'top_products': top_products,
    })


@login_required
@require_POST
def cancel_order(request, order_id):
    """Pending order ah mattum cancel pannum, stock thirumba serkkum."""
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(), id=order_id, customer=request.user
        )
        if order.status == 'pending':
            product = order.product
            product.stock_quantity += order.quantity
            product.save()
            order.status = 'cancelled'
            order.save()
    return redirect('my_orders')


@login_required
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'my_orders.html', {'orders': orders})


# ---------------- Pack size chooser (product detail page) ----------------

SIZE_FACTORS = {
    'kg': 1000, 'g': 1, 'gm': 1, 'gms': 1,
    'l': 1000, 'lit': 1000, 'ltr': 1000, 'litre': 1000, 'liter': 1000,
    'ml': 1,
    'pcs': 1, 'pc': 1, 'pack': 1,
}


def size_sort_key(text):
    """'1/2 L' -> 500, '1 L' -> 1000, '500 g' -> 500, 'Rs 10 pack' -> 0 (sorted by price after)."""
    value = (text or '').lower().replace(' ', '')
    match = re.match(r'^(?:(\d+)/(\d+)|(\d+(?:\.\d+)?))([a-z]*)', value)
    if not match:
        return 0
    if match.group(1):
        number = int(match.group(1)) / int(match.group(2))
    else:
        number = float(match.group(3))
    return number * SIZE_FACTORS.get(match.group(4), 1)


def get_siblings(product):
    """All products in the same variant_group, smallest size first. Empty if no group."""
    if not product.variant_group:
        return []
    siblings = list(
        Product.objects.filter(variant_group=product.variant_group)
        .prefetch_related('images')
    )
    siblings.sort(key=lambda p: (size_sort_key(p.chip_label), p.price))
    return siblings


def serialize_variant(product):
    """Data the product detail page needs to switch sizes without a page reload."""
    images = []
    if product.image:
        images.append(product.image.url)
    for extra in product.images.all():
        if extra.image:
            images.append(extra.image.url)
    mrp = float(product.mrp or product.price)
    price = float(product.price)
    return {
        'id': product.pk,
        'label': product.chip_label,
        'pack_size': product.pack_size or product.chip_label,
        'name': product.name,
        'price': price,
        'mrp': mrp,
        'save': round(mrp - price),
        'percent': product.discount_percent,
        'unit_text': product.price_per_unit,
        'stock': product.stock_quantity,
        'images': images,
        'url': reverse('product_detail', args=[product.pk]),
    }


class ProductDetailView(DetailView):
    model = Product
    template_name = 'product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['similar_products'] = (
            Product.objects.filter(category=self.object.category)
            .exclude(pk=self.object.pk)[:10]
        )

        siblings = get_siblings(self.object)
        if len(siblings) > 1:
            context['variants'] = [serialize_variant(p) for p in siblings]
        else:
            context['variants'] = []
        context['current_id'] = self.object.pk
        return context
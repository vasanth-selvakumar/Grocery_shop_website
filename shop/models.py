from django.contrib.auth.models import AbstractUser
from django.db import models
import random


class CustomUser(AbstractUser):
    mobile_number = models.CharField(max_length=15, unique=True)


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    mrp = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    min_stock = models.PositiveIntegerField(default=5)      # ithukku keela pona "Low stock"
    max_stock = models.PositiveIntegerField(default=500)    # maximum ethana vaipeenga

    @property
    def discount_percent(self):
        if self.mrp and self.mrp > self.price:
            return int(round((self.mrp - self.price) * 100 / self.mrp))
        return 0

    @property
    def discount_amount(self):
        if self.mrp and self.mrp > self.price:
            return self.mrp - self.price
        return 0

    def __str__(self):
        return self.name


# Delivery slots: (key, label, slot start hour, slot end hour)
# Views la intha list use pannalaam (neram dhaandina slot-a hide panna)
DELIVERY_SLOTS = [
    ('morning', 'Morning (9 AM - 12 PM)', 9, 12),
    ('afternoon', 'Afternoon (12 PM - 4 PM)', 12, 16),
    ('evening', 'Evening (4 PM - 8 PM)', 16, 20),
]
DELIVERY_SLOT_CHOICES = [(key, label) for key, label, start, end in DELIVERY_SLOTS]


class Order(models.Model):
    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
    ]
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    address = models.TextField()
    delivery_otp = models.CharField(max_length=6, blank=True, null=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cod')
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_charge = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Delivery slot (pazhaya orders-ku kaali-a irukkum)
    delivery_date = models.DateField(blank=True, null=True)
    delivery_slot = models.CharField(max_length=20, choices=DELIVERY_SLOT_CHOICES, blank=True)

    def generate_otp(self):
        self.delivery_otp = str(random.randint(1000, 9999))
        self.save()

    @property
    def delivery_slot_text(self):
        """Templates la kaatrathukku: 'Today, Evening (4 PM - 8 PM)' maari."""
        if not self.delivery_date or not self.delivery_slot:
            return ''
        from datetime import date, timedelta
        today = date.today()
        if self.delivery_date == today:
            day = 'Today'
        elif self.delivery_date == today + timedelta(days=1):
            day = 'Tomorrow'
        else:
            day = self.delivery_date.strftime('%d %b')
        return f"{day}, {self.get_delivery_slot_display()}"

    def __str__(self):
        return f"{self.customer} - {self.product.name} ({self.quantity})"


class Address(models.Model):
    """Customer oda saved delivery addresses (Home, Shop, etc.)."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=30, default='Home')
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.label}"


class Cart(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return sum(item.subtotal() for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    def subtotal(self):
        return self.product.price * self.quantity


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/gallery/')

    def __str__(self):
        return f"{self.product.name} - extra image"
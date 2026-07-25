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
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=8, decimal_places=2)
   

    def __str__(self):
        return self.name

from django.contrib.auth import get_user_model

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
    ]
    customer = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_otp = models.CharField(max_length=6, blank=True, null=True)
    ordered_at = models.DateTimeField(auto_now_add=True)


    def generate_otp(self):
        self.delivery_otp = str(random.randint(1000, 9999))
        self.save()

    def __str__(self):
        return f"{self.customer} - {self.product.name} ({self.quantity})"        



# Create your models here.

from django.urls import path
from .views import ProductListView
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView


urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('order/<int:product_id>/', views.place_order, name='place_order'),
    path('order/success/', views.order_success, name='order_success'),
    path('signup/', views.signup_view, name='signup'),
    path('verify-delivery/', views.verify_delivery, name='verify_delivery'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('checkout/', views.checkout, name='checkout'),
]
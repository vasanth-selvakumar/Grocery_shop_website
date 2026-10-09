from django.urls import path
from .views import ProductListView,ProductDetailView
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('order/<int:product_id>/', views.place_order, name='place_order'),
    path('order/success/', views.order_success, name='order_success'),
    path('signup/', views.signup_view, name='signup'),
    path('verify-delivery/', views.verify_delivery, name='verify_delivery'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/ajax/<int:product_id>/', views.cart_ajax, name='cart_ajax'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/buy-again/<int:order_id>/', views.buy_again, name='buy_again'),
    path('checkout/', views.checkout, name='checkout'),
    path('dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('dashboard/stock/', views.stock_dashboard, name='stock_dashboard'),
    path('dashboard/bill/<int:order_id>/', views.print_bill, name='print_bill'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('sales-report/', views.sales_report, name='sales_report'),
]
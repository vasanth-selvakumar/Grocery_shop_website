from django.urls import path
from .views import ProductListView
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('order/<int:product_id>/', views.place_order, name='place_order'),
    path('order/success/', views.order_success, name='order_success'),
    path('signup/', views.signup_view, name='signup'),
    path('verify-delivery/', views.verify_delivery, name='verify_delivery'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='product_list'), name='logout'),
]
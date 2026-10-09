from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Category, Product, Order, ProductImage
from .utils import send_delivery_otp


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('mobile_number',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('mobile_number',)}),
    )


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'product', 'quantity', 'status', 'payment_method', 'delivery_charge')

    def save_model(self, request, obj, form, change):
        if change:
            old_status = Order.objects.get(pk=obj.pk).status
            if old_status != 'out_for_delivery' and obj.status == 'out_for_delivery':
                obj.generate_otp()
                send_delivery_otp(obj)
        super().save_model(request, obj, form, change)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3


@admin.action(description='Set Min stock = 200 for selected products')
def set_min_stock_200(modeladmin, request, queryset):
    queryset.update(min_stock=200)


@admin.action(description='Set Max stock = 500 for selected products')
def set_max_stock_500(modeladmin, request, queryset):
    queryset.update(max_stock=500)


class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'mrp', 'price', 'stock_quantity', 'min_stock', 'max_stock', 'expiry_date')
    list_editable = ('mrp', 'price', 'stock_quantity', 'min_stock', 'max_stock')
    list_filter = ('category',)
    search_fields = ('name',)
    actions = [set_min_stock_200, set_max_stock_500]
    inlines = [ProductImageInline]


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Category)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
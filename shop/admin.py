import re
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.text import slugify

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
    list_display = ('id', 'customer', 'product', 'quantity', 'status',
                    'payment_method', 'delivery_charge')

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


SIZE_RE = re.compile(r'\s*1\s*kg', re.IGNORECASE)


def half_of(value):
    if value is None:
        return None
    return (Decimal(value) / 2).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


@admin.action(description='Create 500 g copy of selected 1 kg products')
def create_500g_variant(modeladmin, request, queryset):
    created = []
    skipped = []

    for p in queryset:
        if not SIZE_RE.search(p.name):
            skipped.append(p.name)
            continue

        new_name = SIZE_RE.sub(' 500g', p.name).strip()
        if Product.objects.filter(name__iexact=new_name).exists():
            skipped.append(p.name)
            continue

        group = p.variant_group
        if not group:
            group = slugify(SIZE_RE.sub('', p.name))
            p.variant_group = group
            p.save(update_fields=['variant_group'])

        new_product = Product.objects.create(
            name=new_name,
            category=p.category,
            price=half_of(p.price),
            mrp=half_of(p.mrp),
            image=p.image,
            expiry_date=p.expiry_date,
            stock_quantity=0,
            min_stock=p.min_stock,
            max_stock=p.max_stock,
            brand=p.brand,
            description=p.description,
            variant_group=group,
        )

        for extra in ProductImage.objects.filter(product=p):
            ProductImage.objects.create(product=new_product, image=extra.image)

        created.append(new_name)

    message = '%d created: %s.' % (len(created), ', '.join(created) or 'none')
    if skipped:
        message += ' Skipped: %s.' % ', '.join(skipped)
    message += ' Now set the exact price and stock for each new product.'
    modeladmin.message_user(request, message)


class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'mrp', 'price', 'stock_quantity',
        'min_stock', 'max_stock', 'expiry_date', 'variant_group',
    )
    list_editable = (
        'mrp', 'price', 'stock_quantity', 'min_stock', 'max_stock',
        'variant_group',
    )
    list_filter = ('category',)
    search_fields = ('name', 'variant_group')
    actions = [set_min_stock_200, set_max_stock_500, create_500g_variant]
    inlines = [ProductImageInline]


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Category)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
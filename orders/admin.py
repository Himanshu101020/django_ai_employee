from django.contrib import admin
from .models import Product, Order, RefundRequest


class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'in_stock']

class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'product_name', 'amount', 'delivery', 'carrier', 'status']
    list_filter = ['user', 'product', 'status']
    search_fields = ['user__username', 'product_name', 'status']

class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'order', 'status']

admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(RefundRequest, RefundRequestAdmin)
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from .models import Category, Product, ProductMovement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin para el modelo Category"""
    list_display = ('name', 'company', 'is_active', 'created_at')
    list_filter = ('is_active', 'company')
    search_fields = ('name', 'description')
    ordering = ('company', 'name')
    
    def get_queryset(self, request):
        """Filtra categorías según el usuario"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Si no es superusuario, solo ve categorías de su empresa
        return qs.filter(company=request.user.company)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtra empresas disponibles según usuario"""
        if db_field.name == "company" and not request.user.is_superuser:
            kwargs["queryset"] = request.user.company.__class__.objects.filter(pk=request.user.company.pk)
            kwargs["initial"] = request.user.company
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    """Admin para el modelo Product con capacidad de importación/exportación"""
    list_display = ('name', 'sku', 'category', 'stock', 'min_stock', 'is_active')
    list_filter = ('is_active', 'category', 'company')
    search_fields = ('name', 'description', 'sku', 'barcode')
    readonly_fields = ('stock',)
    list_editable = ('min_stock',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'image')
        }),
        (_('Categorización'), {
            'fields': ('category', 'company')
        }),
        (_('Códigos'), {
            'fields': ('sku', 'barcode')
        }),
        (_('Precios'), {
            'fields': ('cost_price', 'selling_price')
        }),
        (_('Inventario'), {
            'fields': ('stock', 'min_stock', 'max_stock', 'location')
        }),
        (_('Estado'), {
            'fields': ('is_active',)
        }),
    )
    
    def get_queryset(self, request):
        """Filtra productos según el usuario"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Si no es superusuario, solo ve productos de su empresa
        return qs.filter(company=request.user.company)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtra empresas y categorías disponibles según usuario"""
        if not request.user.is_superuser:
            if db_field.name == "company":
                kwargs["queryset"] = request.user.company.__class__.objects.filter(pk=request.user.company.pk)
                kwargs["initial"] = request.user.company
            elif db_field.name == "category":
                kwargs["queryset"] = Category.objects.filter(company=request.user.company)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ProductMovementInline(admin.TabularInline):
    """Inline para ver movimientos en la página de detalle de un producto"""
    model = ProductMovement
    extra = 0
    readonly_fields = ('type', 'quantity', 'reason', 'reference', 'created_by', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProductMovement)
class ProductMovementAdmin(admin.ModelAdmin):
    """Admin para el modelo ProductMovement"""
    list_display = ('product', 'quantity', 'type', 'reason', 'created_by', 'created_at')
    list_filter = ('type', 'reason', 'created_at', 'company')
    search_fields = ('product__name', 'reference', 'notes')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('product', 'quantity', 'type', 'reason')
        }),
        (_('Información adicional'), {
            'fields': ('reference', 'notes')
        }),
        (_('Sistema'), {
            'fields': ('company', 'created_by', 'created_at')
        }),
    )
    
    def get_queryset(self, request):
        """Filtra movimientos según el usuario"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Si no es superusuario, solo ve movimientos de su empresa
        return qs.filter(company=request.user.company)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtra opciones disponibles según usuario"""
        if not request.user.is_superuser:
            if db_field.name == "company":
                kwargs["queryset"] = request.user.company.__class__.objects.filter(pk=request.user.company.pk)
                kwargs["initial"] = request.user.company
            elif db_field.name == "product":
                kwargs["queryset"] = Product.objects.filter(company=request.user.company)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Asigna el usuario actual al crear un movimiento"""
        if not change:  # Solo para nuevos objetos
            obj.created_by = request.user
            if not obj.company:
                obj.company = request.user.company
        super().save_model(request, obj, form, change)


# Añadir inline de movimientos al admin de Producto
ProductAdmin.inlines = [ProductMovementInline]
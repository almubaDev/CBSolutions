from django.db import models
from django.utils.translation import gettext_lazy as _
from system.models import Company, User


class Category(models.Model):
    """
    Modelo para categorías de productos.
    Cada categoría pertenece a una empresa específica.
    """
    name = models.CharField(_("Nombre"), max_length=100)
    description = models.TextField(_("Descripción"), blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name=_("Empresa")
    )
    is_active = models.BooleanField(_("Activo"), default=True)
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de Actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Categoría")
        verbose_name_plural = _("Categorías")
        ordering = ["name"]
        # Garantiza que no haya categorías duplicadas para la misma empresa
        unique_together = [["company", "name"]]
        
    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Modelo para productos en el inventario.
    Cada producto pertenece a una categoría y empresa.
    """
    name = models.CharField(_("Nombre"), max_length=150)
    description = models.TextField(_("Descripción"), blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Categoría")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("Empresa")
    )
    sku = models.CharField(_("SKU"), max_length=50, blank=True)
    barcode = models.CharField(_("Código de Barras"), max_length=50, blank=True)
    cost_price = models.DecimalField(
        _("Precio de Costo"),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    selling_price = models.DecimalField(
        _("Precio de Venta"),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    stock = models.DecimalField(
        _("Stock Actual"),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    min_stock = models.DecimalField(
        _("Stock Mínimo"),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    max_stock = models.DecimalField(
        _("Stock Máximo"),
        max_digits=10,
        decimal_places=2,
        default=0,
        blank=True
    )
    location = models.CharField(_("Ubicación"), max_length=100, blank=True)
    image = models.ImageField(
        _("Imagen"),
        upload_to="products/",
        blank=True,
        null=True
    )
    is_active = models.BooleanField(_("Activo"), default=True)
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de Actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Producto")
        verbose_name_plural = _("Productos")
        ordering = ["name"]
        # Garantiza que no haya SKUs duplicados para la misma empresa
        unique_together = [["company", "sku"]]
        
    def __str__(self):
        return self.name
    
    def is_low_stock(self):
        """Verifica si el producto está por debajo del stock mínimo"""
        return self.stock < self.min_stock
    
    def get_profit(self):
        """Calcula el margen de ganancia por unidad"""
        if self.cost_price:
            return self.selling_price - self.cost_price
        return self.selling_price
    
    def get_profit_percentage(self):
        """Calcula el porcentaje de ganancia"""
        if self.cost_price and self.cost_price > 0:
            return ((self.selling_price - self.cost_price) / self.cost_price) * 100
        return 0


class ProductMovement(models.Model):
    """
    Modelo para registrar movimientos de productos (entradas y salidas).
    """
    TYPE_CHOICES = [
        ('IN', _('Entrada')),
        ('OUT', _('Salida')),
    ]
    
    REASON_CHOICES = [
        ('PURCHASE', _('Compra')),
        ('SALE', _('Venta')),
        ('RETURN', _('Devolución')),
        ('ADJUSTMENT', _('Ajuste de Inventario')),
        ('TRANSFER', _('Transferencia')),
        ('OTHER', _('Otro')),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name=_("Producto")
    )
    quantity = models.DecimalField(
        _("Cantidad"),
        max_digits=10,
        decimal_places=2
    )
    type = models.CharField(
        _("Tipo"),
        max_length=3,
        choices=TYPE_CHOICES
    )
    reason = models.CharField(
        _("Motivo"),
        max_length=20,
        choices=REASON_CHOICES,
        default='OTHER'
    )
    reference = models.CharField(_("Referencia"), max_length=100, blank=True)
    notes = models.TextField(_("Notas"), blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="product_movements",
        verbose_name=_("Empresa")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="product_movements",
        verbose_name=_("Creado por")
    )
    created_at = models.DateTimeField(_("Fecha"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Movimiento de Producto")
        verbose_name_plural = _("Movimientos de Productos")
        ordering = ["-created_at"]
        
    def __str__(self):
        return f"{self.get_type_display()} - {self.product.name} ({self.quantity})"
    
    def save(self, *args, **kwargs):
        # Actualizar el stock del producto
        if self.pk is None:  # Solo para nuevos movimientos
            if self.type == 'IN':
                self.product.stock += self.quantity
            else:  # 'OUT'
                self.product.stock -= self.quantity
            self.product.save()
        super().save(*args, **kwargs)
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Category, Product, ProductMovement


class CategoryForm(forms.ModelForm):
    """Formulario para crear y editar categorías"""
    class Meta:
        model = Category
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        """Validar que el nombre sea único en la empresa"""
        name = self.cleaned_data.get('name')
        # Verificar si ya existe una categoría con el mismo nombre en esta empresa
        queryset = Category.objects.filter(company=self.company, name=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError(_('Ya existe una categoría con este nombre en tu empresa.'))
        return name

    def save(self, commit=True):
        """Asignar la empresa al guardar"""
        instance = super().save(commit=False)
        if self.company and not instance.company_id:
            instance.company = self.company
        if commit:
            instance.save()
        return instance


class ProductForm(forms.ModelForm):
    """Formulario para crear y editar productos"""
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 'sku', 'barcode',
            'cost_price', 'selling_price', 'min_stock', 'max_stock',
            'location', 'image', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar categorías por empresa
        if self.company:
            self.fields['category'].queryset = Category.objects.filter(
                company=self.company, is_active=True
            )

    def clean_sku(self):
        """Validar que el SKU sea único en la empresa"""
        sku = self.cleaned_data.get('sku')
        if not sku:  # Si está vacío, no validar unicidad
            return sku
            
        # Verificar si ya existe un producto con el mismo SKU en esta empresa
        queryset = Product.objects.filter(company=self.company, sku=sku)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError(_('Ya existe un producto con este SKU en tu empresa.'))
        return sku

    def save(self, commit=True):
        """Asignar la empresa al guardar"""
        instance = super().save(commit=False)
        if self.company and not instance.company_id:
            instance.company = self.company
        if commit:
            instance.save()
        return instance


class ProductMovementForm(forms.ModelForm):
    """Formulario para registrar movimientos de inventario"""
    class Meta:
        model = ProductMovement
        fields = ['product', 'quantity', 'type', 'reason', 'reference', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar productos por empresa
        if self.company:
            self.fields['product'].queryset = Product.objects.filter(
                company=self.company, is_active=True
            )
            
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.company:
            instance.company = self.company
        if self.user:
            instance.created_by = self.user
        if commit:
            instance.save()
        return instance


class StockAdjustmentForm(forms.ModelForm):
    """Formulario para ajustes rápidos de inventario"""
    class Meta:
        model = ProductMovement
        fields = ['product', 'quantity', 'type', 'reason', 'reference', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Número de documento o referencia')}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Observaciones adicionales')}),
        }
        
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar productos por empresa
        if self.company:
            self.fields['product'].queryset = Product.objects.filter(
                company=self.company, is_active=True
            )
            
        # Establecer valores predeterminados
        self.fields['reason'].initial = 'ADJUSTMENT'
        self.fields['reference'].initial = _('Ajuste manual')
        
        # Añadir clases y place holders adicionales
        self.fields['product'].widget.attrs['class'] += ' select2'  # Usar select2 para mejor UX
        self.fields['reason'].widget.attrs['readonly'] = True  # El motivo siempre es ajuste
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.company:
            instance.company = self.company
        if self.user:
            instance.created_by = self.user
        # Siempre es un ajuste de inventario
        instance.reason = 'ADJUSTMENT'
        if commit:
            instance.save()
        return instance
    
    
class ExportForm(forms.Form):
    """
    Formulario para configurar la exportación de datos de inventario.
    """
    # Formato de exportación
    export_format = forms.ChoiceField(
        label=_("Formato de exportación"),
        choices=[('excel', _('Excel')), ('pdf', _('PDF'))],
        initial='excel',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # Filtros principales
    category = forms.ModelChoiceField(
        label=_("Categoría"),
        queryset=Category.objects.none(),  # Se llenará en __init__
        required=False,
        empty_label=_("Todas las categorías"),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    stock_status = forms.ChoiceField(
        label=_("Estado de stock"),
        choices=[
            ('', _('Todos los productos')),
            ('low', _('Stock bajo')),
            ('out', _('Sin stock')),
            ('ok', _('Stock adecuado'))
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search_query = forms.CharField(
        label=_("Buscar productos"),
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Nombre, SKU, código de barras...')})
    )
    
    # Contenido a incluir
    include_movements = forms.BooleanField(
        label=_("Incluir historial de movimientos"),
        required=False,
        initial=False,
        help_text=_("Añade una hoja adicional con los últimos movimientos de cada producto"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    include_images = forms.BooleanField(
        label=_("Incluir imágenes de productos"),
        required=False,
        initial=False,
        help_text=_("Solo disponible para exportación PDF"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Opciones de columnas (solo para Excel)
    columns = forms.MultipleChoiceField(
        label=_("Columnas a incluir"),
        choices=[
            ('sku', _('SKU')),
            ('barcode', _('Código de barras')),
            ('category', _('Categoría')),
            ('cost_price', _('Precio de costo')),
            ('selling_price', _('Precio de venta')),
            ('stock', _('Stock actual')),
            ('min_stock', _('Stock mínimo')),
            ('max_stock', _('Stock máximo')),
            ('location', _('Ubicación')),
            ('description', _('Descripción')),
            ('is_active', _('Estado')),
            ('last_movement', _('Último movimiento')),
        ],
        initial=['sku', 'category', 'cost_price', 'selling_price', 'stock', 'min_stock'],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    # Opciones avanzadas de formato
    page_size = forms.ChoiceField(
        label=_("Tamaño de página (PDF)"),
        choices=[
            ('a4', _('A4')),
            ('letter', _('Carta')),
            ('legal', _('Legal'))
        ],
        initial='a4',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    orientation = forms.ChoiceField(
        label=_("Orientación (PDF)"),
        choices=[
            ('portrait', _('Vertical')),
            ('landscape', _('Horizontal'))
        ],
        initial='portrait',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Opciones técnicas
    process_async = forms.BooleanField(
        label=_("Procesar en segundo plano"),
        required=False,
        initial=False,
        help_text=_("Recomendado para grandes volúmenes de datos (más de 500 productos)"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    use_cache = forms.BooleanField(
        label=_("Usar caché si existe"),
        required=False,
        initial=True,
        help_text=_("Utilizar exportación reciente si está disponible (hasta 1 hora)"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    add_watermark = forms.BooleanField(
        label=_("Añadir marca de agua"),
        required=False,
        initial=False,
        help_text=_("Solo para PDF. Añade un texto diagonal con fecha y usuario"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    include_header_footer = forms.BooleanField(
        label=_("Incluir encabezado y pie de página"),
        required=False,
        initial=True,
        help_text=_("Añade logo de empresa, fecha de generación y numeración"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar categorías por empresa
        if self.company:
            self.fields['category'].queryset = Category.objects.filter(
                company=self.company, is_active=True
            ).order_by('name')
        
        # Ajustar campos dependiendo del formato seleccionado
        if args and args[0]:
            if args[0].get('export_format') == 'pdf':
                self.fields['columns'].widget.attrs['disabled'] = True
                self.fields['columns'].help_text = _("La selección de columnas solo está disponible para Excel")
            else:  # excel
                self.fields['add_watermark'].widget.attrs['disabled'] = True
                self.fields['page_size'].widget.attrs['disabled'] = True
                self.fields['orientation'].widget.attrs['disabled'] = True
                self.fields['include_images'].widget.attrs['disabled'] = True
                self.fields['include_images'].help_text = _("Las imágenes solo están disponibles en formato PDF")
    
    def clean(self):
        cleaned_data = super().clean()
        export_format = cleaned_data.get('export_format')
        
        # Validar opciones específicas de formato
        if export_format == 'excel':
            # Requerir al menos una columna para Excel
            columns = cleaned_data.get('columns', [])
            if not columns:
                self.add_error('columns', _("Debes seleccionar al menos una columna"))
            
            # Limpiar opciones que no aplican
            cleaned_data['add_watermark'] = False
            cleaned_data['page_size'] = 'a4'  # valor por defecto
            cleaned_data['orientation'] = 'portrait'  # valor por defecto
            cleaned_data['include_images'] = False
            
        elif export_format == 'pdf':
            # Para PDF, determinar un conjunto de columnas estándar
            cleaned_data['columns'] = ['sku', 'category', 'cost_price', 'selling_price', 'stock', 'min_stock']
        
        return cleaned_data
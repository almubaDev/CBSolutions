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
            'reason': forms.Select(attrs={'class': 'form-
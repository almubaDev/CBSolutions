from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Sum, F, Value, CharField
from django.db.models.functions import Concat
from .models import Category, Product, ProductMovement
from .forms import CategoryForm, ProductForm, ProductMovementForm, StockAdjustmentForm


class InventoryUserMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin para verificar que el usuario tiene acceso al módulo de inventario.
    """
    def test_func(self):
        user = self.request.user
        # Superusuarios tienen acceso a todo
        if user.is_superuser:
            return True
        # Verificar que el usuario tenga empresa y que tenga módulo de inventario activo
        return user.company and user.company.module_inventory


# --- Vistas para Categorías ---

class CategoryListView(InventoryUserMixin, ListView):
    """
    Lista de categorías de productos.
    """
    model = Category
    template_name = 'inventory/categories/category_list.html'
    context_object_name = 'categories'
    paginate_by = 10
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = Category.objects.all()
        
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
            
        # Búsqueda por nombre o descripción
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Categorías')
        context['search_query'] = self.request.GET.get('q', '')
        # Contador de productos por categoría
        categories_with_counts = []
        for category in context['categories']:
            count = Product.objects.filter(category=category).count()
            categories_with_counts.append((category, count))
        context['categories_with_counts'] = categories_with_counts
        return context


class CategoryCreateView(InventoryUserMixin, CreateView):
    """
    Crear una nueva categoría de productos.
    """
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/categories/category_form.html'
    success_url = reverse_lazy('inventory:category_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs
    
    def form_valid(self, form):
        """Asignar la empresa del usuario actual"""
        if not self.request.user.is_superuser:
            form.instance.company = self.request.user.company
        messages.success(self.request, _('Categoría creada correctamente.'))
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Crear Categoría')
        return context


class CategoryUpdateView(InventoryUserMixin, UpdateView):
    """
    Actualizar una categoría existente.
    """
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/categories/category_form.html'
    success_url = reverse_lazy('inventory:category_list')
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        return queryset
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, _('Categoría actualizada correctamente.'))
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Editar Categoría')
        return context


class CategoryDeleteView(InventoryUserMixin, DeleteView):
    """
    Eliminar una categoría.
    """
    model = Category
    template_name = 'inventory/categories/category_confirm_delete.html'
    success_url = reverse_lazy('inventory:category_list')
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        return queryset
    
    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, _('Categoría eliminada correctamente.'))
            return response
        except:
            messages.error(request, _('No se puede eliminar la categoría porque tiene productos asociados.'))
            return redirect('inventory:category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Eliminar Categoría')
        # Verificar si tiene productos
        context['has_products'] = Product.objects.filter(category=self.object).exists()
        context['products_count'] = Product.objects.filter(category=self.object).count()
        return context


# --- Vistas para Productos ---

class ProductListView(InventoryUserMixin, ListView):
    """
    Lista de productos.
    """
    model = Product
    template_name = 'inventory/products/product_list.html'
    context_object_name = 'products'
    paginate_by = 15
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = Product.objects.all()
        
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        
        # Filtro por categoría
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filtro por estado de stock
        stock_status = self.request.GET.get('stock_status')
        if stock_status == 'low':
            queryset = queryset.filter(stock__lt=F('min_stock'))
        elif stock_status == 'out':
            queryset = queryset.filter(stock=0)
        elif stock_status == 'ok':
            queryset = queryset.filter(
                stock__gte=F('min_stock'),
                stock__gt=0
            )
        
        # Búsqueda
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(barcode__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Productos')
        
        # Parámetros de filtro para conservarlos en paginación
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['stock_status'] = self.request.GET.get('stock_status', '')
        
        # Listado de categorías para filtro
        if self.request.user.is_superuser:
            context['categories'] = Category.objects.all()
        else:
            context['categories'] = Category.objects.filter(
                company=self.request.user.company
            )
        
        # Resumen de estado de inventario
        if self.request.user.is_superuser and not self.request.user.company:
            # No mostrar resumen para superusuarios sin empresa
            context['show_summary'] = False
        else:
            company = self.request.user.company
            context['show_summary'] = True
            context['total_products'] = Product.objects.filter(company=company).count()
            context['low_stock_count'] = Product.objects.filter(
                company=company,
                stock__lt=F('min_stock'),
                stock__gt=0
            ).count()
            context['out_of_stock_count'] = Product.objects.filter(
                company=company,
                stock=0
            ).count()
        
        return context


class ProductDetailView(InventoryUserMixin, DetailView):
    """
    Ver detalles de un producto.
    """
    model = Product
    template_name = 'inventory/products/product_detail.html'
    context_object_name = 'product'
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.object.name
        
        # Obtener últimos movimientos del producto
        context['movements'] = ProductMovement.objects.filter(
            product=self.object
        ).order_by('-created_at')[:10]
        
        return context


class ProductCreateView(InventoryUserMixin, CreateView):
    """
    Crear un nuevo producto.
    """
    model = Product
    form_class = ProductForm
    template_name = 'inventory/products/product_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs
    
    def form_valid(self, form):
        """Asignar la empresa del usuario actual"""
        if not self.request.user.is_superuser:
            form.instance.company = self.request.user.company
        messages.success(self.request, _('Producto creado correctamente.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        if 'save_and_add_movement' in self.request.POST:
            return reverse('inventory:product_add_movement', kwargs={'pk': self.object.pk})
        else:
            return reverse('inventory:product_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Crear Producto')
        return context


class ProductUpdateView(InventoryUserMixin, UpdateView):
    """
    Actualizar un producto existente.
    """
    model = Product
    form_class = ProductForm
    template_name = 'inventory/products/product_form.html'
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        return queryset
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, _('Producto actualizado correctamente.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('inventory:product_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Editar Producto')
        return context


class ProductDeleteView(InventoryUserMixin, DeleteView):
    """
    Eliminar un producto.
    """
    model = Product
    template_name = 'inventory/products/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        return queryset
    
    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, _('Producto eliminado correctamente.'))
            return response
        except:
            messages.error(request, _('No se puede eliminar el producto porque tiene movimientos asociados.'))
            return redirect('inventory:product_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Eliminar Producto')
        # Verificar si tiene movimientos
        context['has_movements'] = ProductMovement.objects.filter(product=self.object).exists()
        context['movements_count'] = ProductMovement.objects.filter(product=self.object).count()
        return context


# --- Vistas para Movimientos de Productos ---

@login_required
def add_product_movement(request, pk):
    """
    Añadir un movimiento a un producto específico.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    # Obtener el producto
    if user.is_superuser:
        product = get_object_or_404(Product, pk=pk)
    else:
        product = get_object_or_404(Product, pk=pk, company=user.company)
    
    if request.method == 'POST':
        form = ProductMovementForm(
            request.POST, 
            company=user.company, 
            user=user
        )
        if form.is_valid():
            movement = form.save(commit=False)
            movement.product = product
            if not user.is_superuser:
                movement.company = user.company
            movement.created_by = user
            movement.save()
            messages.success(request, _('Movimiento registrado correctamente.'))
            return redirect('inventory:product_detail', pk=product.pk)
    else:
        # Preseleccionar el producto
        form = ProductMovementForm(
            initial={'product': product}, 
            company=user.company, 
            user=user
        )
        # Deshabilitar el campo de producto ya que viene de la URL
        form.fields['product'].widget.attrs['disabled'] = True
    
    context = {
        'title': _('Registrar Movimiento'),
        'form': form,
        'product': product,
    }
    return render(request, 'inventory/movements/movement_form.html', context)


class MovementListView(InventoryUserMixin, ListView):
    """
    Lista de movimientos de productos.
    """
    model = ProductMovement
    template_name = 'inventory/movements/movement_list.html'
    context_object_name = 'movements'
    paginate_by = 20
    
    def get_queryset(self):
        """Filtrar por empresa del usuario"""
        queryset = ProductMovement.objects.all()
        
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)
        
        # Filtros
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        movement_type = self.request.GET.get('type')
        if movement_type:
            queryset = queryset.filter(type=movement_type)
        
        reason = self.request.GET.get('reason')
        if reason:
            queryset = queryset.filter(reason=reason)
        
        # Filtro por fecha
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Búsqueda
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) | 
                Q(reference__icontains=search_query) |
                Q(notes__icontains=search_query)
            )
        
        return queryset.select_related('product', 'created_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Movimientos de Inventario')
        
        # Parámetros de filtro para conservarlos en paginación
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_product'] = self.request.GET.get('product', '')
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_reason'] = self.request.GET.get('reason', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Listado de productos para filtro
        if self.request.user.is_superuser:
            context['products'] = Product.objects.all()
        else:
            context['products'] = Product.objects.filter(
                company=self.request.user.company
            )
        
        # Opciones para filtros
        context['type_choices'] = ProductMovement.TYPE_CHOICES
        context['reason_choices'] = ProductMovement.REASON_CHOICES
        
        return context


@login_required
def stock_adjustment(request):
    """
    Vista para ajustes rápidos de inventario.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    if request.method == 'POST':
        form = StockAdjustmentForm(
            request.POST, 
            company=user.company, 
            user=user
        )
        if form.is_valid():
            movement = form.save(commit=False)
            if not user.is_superuser:
                movement.company = user.company
            movement.created_by = user
            movement.save()
            messages.success(request, _('Ajuste de inventario realizado correctamente.'))
            return redirect('inventory:product_detail', pk=movement.product.pk)
    else:
        form = StockAdjustmentForm(
            company=user.company, 
            user=user
        )
    
    context = {
        'title': _('Ajuste de Inventario'),
        'form': form,
    }
    return render(request, 'inventory/movements/stock_adjustment_form.html', context)


# --- Vistas de Dashboard de Inventario ---

@login_required
def inventory_dashboard(request):
    """
    Dashboard principal del módulo de inventario.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    # Obtener datos para el dashboard
    if user.is_superuser and not user.company:
        # Superusuario sin empresa asignada
        categories_count = Category.objects.count()
        products_count = Product.objects.count()
        low_stock_count = Product.objects.filter(stock__lt=F('min_stock'), stock__gt=0).count()
        out_of_stock_count = Product.objects.filter(stock=0).count()
        recent_movements = ProductMovement.objects.all().order_by('-created_at')[:10]
    else:
        # Usuario normal o superusuario con empresa
        company = user.company
        categories_count = Category.objects.filter(company=company).count()
        products_count = Product.objects.filter(company=company).count()
        low_stock_count = Product.objects.filter(
            company=company,
            stock__lt=F('min_stock'),
            stock__gt=0
        ).count()
        out_of_stock_count = Product.objects.filter(
            company=company,
            stock=0
        ).count()
        recent_movements = ProductMovement.objects.filter(
            company=company
        ).order_by('-created_at')[:10]
    
    # Productos con stock bajo
    if user.is_superuser and not user.company:
        low_stock_products = Product.objects.filter(
            stock__lt=F('min_stock')
        ).order_by('stock')[:5]
    else:
        company = user.company
        low_stock_products = Product.objects.filter(
            company=company,
            stock__lt=F('min_stock')
        ).order_by('stock')[:5]
    
    context = {
        'title': _('Dashboard de Inventario'),
        'categories_count': categories_count,
        'products_count': products_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'recent_movements': recent_movements,
        'low_stock_products': low_stock_products,
    }
    return render(request, 'inventory/dashboard.html', context)
import io
import csv
import xlsxwriter
from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Sum, F, Value, CharField, Count, Max
from django.db.models.functions import Concat
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.core.cache import cache
from django.template.loader import render_to_string
from .models import Category, Product, ProductMovement
from .forms import CategoryForm, ProductForm, ProductMovementForm, StockAdjustmentForm, ExportForm


@login_required
def export_inventory(request):
    """
    Muestra el formulario para exportar el inventario.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    # Obtener parámetros iniciales si vienen de la lista de productos
    initial_data = {}
    for param in ['category', 'stock_status', 'search_query']:
        if request.GET.get(param):
            initial_data[param] = request.GET.get(param)
    
    if request.method == 'POST':
        form = ExportForm(request.POST, company=user.company)
        if form.is_valid():
            # Determinar la acción según el botón pulsado
            if 'preview' in request.POST:
                # Mostrar vista previa
                return export_preview(request, form.cleaned_data)
            else:
                # Generar exportación directamente
                return generate_export(request, form.cleaned_data)
    else:
        form = ExportForm(initial=initial_data, company=user.company)
    
    context = {
        'title': _('Exportar Inventario'),
        'form': form,
    }
    return render(request, 'inventory/export/export_form.html', context)


@login_required
def export_preview(request, form_data=None):
    """
    Muestra una vista previa de los datos a exportar.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    if not form_data:
        # Si no hay datos de formulario, redirigir al formulario
        return redirect('inventory:export_inventory')
    
    # Obtener datos filtrados
    products = get_filtered_products(request, form_data)
    
    # Limitar a 10-20 productos para la vista previa
    preview_products = products[:15]
    
    context = {
        'title': _('Vista Previa de Exportación'),
        'products': preview_products,
        'total_products': products.count(),
        'columns': form_data.get('columns', []),
        'export_format': form_data.get('export_format', 'excel'),
        'form_data': form_data,  # Pasar todos los datos del formulario
    }
    return render(request, 'inventory/export/export_preview.html', context)


@login_required
def generate_export(request, form_data=None):
    """
    Genera el archivo de exportación basado en los datos del formulario.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    # Si no hay datos de formulario pero hay datos POST o GET, procesar el formulario
    if not form_data:
        if request.method == 'POST':
            form = ExportForm(request.POST, company=user.company)
            if form.is_valid():
                form_data = form.cleaned_data
            else:
                messages.error(request, _('Por favor corrige los errores en el formulario.'))
                return redirect('inventory:export_inventory')
        elif request.GET:
            # Crear datos de formulario a partir de parámetros GET (para exportación rápida)
            form_data = {
                'export_format': request.GET.get('export_format', 'excel'),
                'category': request.GET.get('category', None),
                'stock_status': request.GET.get('stock_status', ''),
                'search_query': request.GET.get('search_query', ''),
                'columns': ['sku', 'category', 'cost_price', 'selling_price', 'stock', 'min_stock'],  # Columnas por defecto
                'include_movements': False,
                'include_images': False,
                'process_async': False,
                'use_cache': True,
                'add_watermark': False,
                'include_header_footer': True,
            }
            
            # Si hay una categoría, convertirla a objeto
            if form_data['category']:
                try:
                    category = Category.objects.get(pk=form_data['category'])
                    form_data['category'] = category
                except:
                    form_data['category'] = None
        else:
            # No hay datos, redirigir al formulario
            return redirect('inventory:export_inventory')
    
    # Obtener datos filtrados
    products = get_filtered_products(request, form_data)
    
    # Generar clave única para caché
    cache_key = f"inventory_export_{request.user.id}_{form_data['export_format']}_{hash(str(products.query))}"
    
    # Verificar caché si está habilitado
    if form_data.get('use_cache', True):
        cached_file = cache.get(cache_key)
        if cached_file:
            # Determinar tipo de contenido y nombre de archivo
            if form_data['export_format'] == 'excel':
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = 'inventory_export.xlsx'
            else:  # pdf
                content_type = 'application/pdf'
                filename = 'inventory_export.pdf'
            
            # Devolver archivo en caché
            response = HttpResponse(cached_file, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    
    # Verificar si se debe procesar en segundo plano
    if form_data.get('process_async', False) and products.count() > 100:
        # Implementar tarea en segundo plano (usando Celery, Django Q, etc.)
        # Por ahora, simularemos que la tarea está en progreso
        
        # Almacenar datos del formulario en la sesión
        request.session['export_form_data'] = form_data
        
        # Redirigir a página de estado
        return redirect('inventory:export_status')
    
    # Procesamiento sincrónico
    if form_data['export_format'] == 'excel':
        response = generate_excel(request, products, form_data)
    else:  # pdf
        response = generate_pdf(request, products, form_data)
    
    # Guardar en caché si está habilitado
    if form_data.get('use_cache', True):
        if hasattr(response, 'content'):
            cache.set(cache_key, response.content, 3600)  # 1 hora
    
    return response


@login_required
def export_status(request):
    """
    Muestra el estado de una exportación en proceso.
    """
    # Verificar acceso al módulo
    user = request.user
    if not user.is_superuser and (not user.company or not user.company.module_inventory):
        messages.error(request, _('No tienes acceso al módulo de inventario.'))
        return redirect('system:dashboard')
    
    # En una implementación real, esto verificaría el estado de la tarea asíncrona
    # Para este ejemplo, simulamos que la tarea está en progreso
    
    context = {
        'title': _('Estado de Exportación'),
        'task_id': 'task_12345',  # ID simulado
        'progress': 50,  # Progreso simulado
        'status': 'processing',  # Estado simulado
    }
    return render(request, 'inventory/export/export_status.html', context)


def get_filtered_products(request, form_data):
    """
    Filtra los productos según los criterios del formulario.
    """
    user = request.user
    
    # Iniciar con todos los productos
    queryset = Product.objects.all()
    
    # Filtrar por empresa
    if not user.is_superuser:
        queryset = queryset.filter(company=user.company)
    
    # Filtrar por categoría
    if form_data.get('category'):
        queryset = queryset.filter(category=form_data['category'])
    
    # Filtrar por estado de stock
    stock_status = form_data.get('stock_status', '')
    if stock_status == 'low':
        queryset = queryset.filter(stock__lt=F('min_stock'), stock__gt=0)
    elif stock_status == 'out':
        queryset = queryset.filter(stock=0)
    elif stock_status == 'ok':
        queryset = queryset.filter(stock__gte=F('min_stock'), stock__gt=0)
    
    # Filtrar por término de búsqueda
    search_query = form_data.get('search_query', '')
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    return queryset


def generate_excel(request, products, form_data):
    """
    Genera un archivo Excel con los datos filtrados.
    """
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet(_('Inventario'))
    
    # Formatos
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#22346e',  # Azul oscuro (color primario)
        'color': 'white',
        'border': 1
    })
    
    cell_format = workbook.add_format({
        'border': 1
    })
    
    number_format = workbook.add_format({
        'border': 1,
        'num_format': '#,##0'
    })
    
    currency_format = workbook.add_format({
        'border': 1,
        'num_format': '$#,##0'
    })
    
    # Definir encabezados según las columnas seleccionadas
    columns = form_data.get('columns', [])
    headers = []
    column_formats = []
    
    # Mapeo de campos a headers y formatos
    column_mapping = {
        'sku': {'header': _('SKU'), 'format': cell_format},
        'barcode': {'header': _('Código de barras'), 'format': cell_format},
        'name': {'header': _('Nombre'), 'format': cell_format},
        'category': {'header': _('Categoría'), 'format': cell_format},
        'cost_price': {'header': _('Precio de costo'), 'format': currency_format},
        'selling_price': {'header': _('Precio de venta'), 'format': currency_format},
        'stock': {'header': _('Stock actual'), 'format': number_format},
        'min_stock': {'header': _('Stock mínimo'), 'format': number_format},
        'max_stock': {'header': _('Stock máximo'), 'format': number_format},
        'location': {'header': _('Ubicación'), 'format': cell_format},
        'description': {'header': _('Descripción'), 'format': cell_format},
        'is_active': {'header': _('Estado'), 'format': cell_format},
        'last_movement': {'header': _('Último movimiento'), 'format': cell_format},
    }
    
    # Siempre incluir el nombre del producto como primera columna
    headers = [_('Nombre')]
    column_formats = [cell_format]
    
    # Añadir encabezados seleccionados
    for col in columns:
        if col in column_mapping and col != 'name':  # 'name' ya está incluido
            headers.append(column_mapping[col]['header'])
            column_formats.append(column_mapping[col]['format'])
    
    # Escribir encabezados
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header, header_format)
    
    # Escribir datos
    for row_num, product in enumerate(products, 1):
        # Primera columna siempre es el nombre
        worksheet.write(row_num, 0, product.name, cell_format)
        
        # Columnas adicionales según selección
        col_num = 1
        for col in columns:
            if col != 'name':  # 'name' ya está incluido
                if col == 'category':
                    value = product.category.name
                elif col == 'is_active':
                    value = _('Activo') if product.is_active else _('Inactivo')
                elif col == 'last_movement':
                    # Obtener el último movimiento
                    last_movement = product.movements.order_by('-created_at').first()
                    if last_movement:
                        value = f"{last_movement.get_type_display()} - {last_movement.quantity} ({last_movement.created_at.strftime('%d/%m/%Y')})"
                    else:
                        value = _('Sin movimientos')
                else:
                    value = getattr(product, col, '')
                
                worksheet.write(row_num, col_num, value, column_formats[col_num])
                col_num += 1
    
    # Ajustar ancho de columnas - CORREGIDO AQUÍ
    for i, unused in enumerate(headers):  # Cambiado _ por unused para evitar conflicto
        worksheet.set_column(i, i, 15)  # 15 caracteres de ancho
    
    # Si se incluyen movimientos, añadir una hoja para ellos
    if form_data.get('include_movements', False):
        movements_sheet = workbook.add_worksheet(_('Movimientos'))
        
        # Encabezados para movimientos
        movement_headers = [
            _('Producto'), _('Tipo'), _('Cantidad'), _('Motivo'), 
            _('Referencia'), _('Fecha'), _('Usuario')
        ]
        
        for col_num, header in enumerate(movement_headers):
            movements_sheet.write(0, col_num, header, header_format)
        
        # Obtener movimientos para los productos filtrados
        movements = ProductMovement.objects.filter(
            product__in=products
        ).order_by('-created_at')[:1000]  # Limitar a 1000 movimientos
        
        # Escribir datos de movimientos
        for row_num, movement in enumerate(movements, 1):
            movements_sheet.write(row_num, 0, movement.product.name, cell_format)
            movements_sheet.write(row_num, 1, movement.get_type_display(), cell_format)
            movements_sheet.write(row_num, 2, movement.quantity, number_format)
            movements_sheet.write(row_num, 3, movement.get_reason_display(), cell_format)
            movements_sheet.write(row_num, 4, movement.reference, cell_format)
            movements_sheet.write(row_num, 5, movement.created_at.strftime('%d/%m/%Y %H:%M'), cell_format)
            movements_sheet.write(row_num, 6, movement.created_by.get_full_name() or movement.created_by.email, cell_format)
        
        # Ajustar ancho de columnas - CORREGIDO AQUÍ
        for i, unused in enumerate(movement_headers):  # Cambiado _ por unused para evitar conflicto
            movements_sheet.set_column(i, i, 15)
    
    # Cerrar libro y preparar respuesta
    workbook.close()
    output.seek(0)
    
    # Preparar respuesta HTTP
    filename = f"inventario_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


def generate_pdf(request, products, form_data):
    """
    Genera un archivo PDF con los datos filtrados.
    """
    # Preparar contexto para la plantilla
    context = {
        'products': products,
        'company': request.user.company if not request.user.is_superuser else None,
        'user': request.user,
        'generated_at': timezone.now(),
        'include_movements': form_data.get('include_movements', False),
        'include_images': form_data.get('include_images', False),
        'include_header_footer': form_data.get('include_header_footer', True),
        'add_watermark': form_data.get('add_watermark', False),
        'page_size': form_data.get('page_size', 'a4'),
        'orientation': form_data.get('orientation', 'portrait'),
    }
    
    # Renderizar plantilla HTML
    html_string = render_to_string('inventory/export/pdf_template.html', context)
    
    # Configurar respuesta
    response = HttpResponse(content_type='application/pdf')
    filename = f"inventario_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Convertir HTML a PDF
    result = create_pdf(html_string, response)
    
    # Verificar si hubo error en la creación del PDF
    if not result:
        messages.error(request, _('Error al generar el PDF.'))
        return redirect('inventory:export_inventory')
    
    return response


def create_pdf(html_string, dest=None):
    """
    Crea un PDF a partir de una cadena HTML.
    """
    # Si no se especifica destino, crear un BytesIO
    if dest is None:
        dest = BytesIO()
        
    # Convertir HTML a PDF con pisa (xhtml2pdf)
    result = pisa.CreatePDF(html_string, dest=dest)
    
    # Si es BytesIO, volver al inicio
    if isinstance(dest, BytesIO):
        dest.seek(0)
    
    return dest if not result.err else None




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
        # Aquí está el cambio clave
        post_data = request.POST.copy()  # Hacer una copia modificable
        post_data['product'] = str(product.pk)  # Agregar el ID del producto
        
        form = ProductMovementForm(
            post_data,  # Usar los datos modificados 
            company=user.company, 
            user=user
        )
        
        if form.is_valid():
            movement = form.save(commit=False)
            # No necesitamos asignar product de nuevo ya que está en el formulario
            if not user.is_superuser:
                movement.company = user.company
            movement.created_by = user
            movement.save()
            messages.success(request, _('Movimiento registrado correctamente.'))
            return redirect('inventory:product_detail', pk=product.pk)
    else:
        form = ProductMovementForm(
            initial={'product': product}, 
            company=user.company, 
            user=user
        )
        
        # Opcional: hacer el campo readonly para que aún se vea pero no se pueda editar
        form.fields['product'].widget.attrs['readonly'] = True
    
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
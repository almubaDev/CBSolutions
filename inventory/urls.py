from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.inventory_dashboard, name='dashboard'),
    
    # Categorías
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # Productos
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('products/<int:pk>/add-movement/', views.add_product_movement, name='product_add_movement'),
    
    # Movimientos
    path('movements/', views.MovementListView.as_view(), name='movement_list'),
    path('stock-adjustment/', views.stock_adjustment, name='stock_adjustment'),
    
    # Exportación de inventario
    path('export/', views.export_inventory, name='export_inventory'),
    path('export/preview/', views.export_preview, name='export_preview'),
    path('export/generate/', views.generate_export, name='generate_export'),
    path('export/status/', views.export_status, name='export_status'),
    
]
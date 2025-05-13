from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'module_inventory', 'module_sales', 'module_purchases', 
                  'module_accounting', 'module_crm', 'module_hrm')
    search_fields = ('name', 'business_name', 'tax_id', 'email')
    fieldsets = (
        (None, {'fields': ('name', 'business_name', 'tax_id', 'is_active')}),
        (_('Información de Contacto'), {'fields': ('address', 'city', 'state', 'country', 
                                                 'postal_code', 'phone', 'email', 'website')}),
        (_('Personalización'), {'fields': ('logo', 'primary_color')}),
        (_('Suscripción'), {'fields': ('max_users', 'subscription_end')}),
        (_('Módulos Activos'), {'fields': ('module_inventory', 'module_sales', 'module_purchases',
                                         'module_accounting', 'module_crm', 'module_hrm')}),
    )
    readonly_fields = ('created_at', 'updated_at')
    
    def get_readonly_fields(self, request, obj=None):
        # Si es creación, no mostrar campos de solo lectura
        if obj is None:
            return []
        return self.readonly_fields


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'company')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Información Personal'), {'fields': ('first_name', 'last_name', 'phone', 'position', 'profile_picture')}),
        (_('Empresa'), {'fields': ('company',)}),
        (_('Permisos'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Preferencias'), {'fields': ('language_preference',)}),
        (_('Fechas Importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'company'),
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        # Si el usuario es superusuario, no mostrar el campo company
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.is_superuser:
            # Crear una copia para no modificar el original
            fieldsets = list(fieldsets)
            # Eliminar la sección 'Empresa'
            fieldsets = [fs for fs in fieldsets if fs[0] != _('Empresa')]
        return fieldsets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponseRedirect
from django.db.models import Q
from .models import User, Company
from .forms import UserProfileForm, CompanyForm, UserForm, LoginForm, PasswordResetRequestForm
from .utils import get_client_ip


class LoginView(TemplateView):
    """
    Vista personalizada para el inicio de sesión.
    Guarda la IP del cliente y redirige según el tipo de usuario.
    """
    template_name = 'system/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Iniciar Sesión')
        context['form'] = LoginForm()
        return context
    
    def post(self, request, *args, **kwargs):
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Guardar la IP de inicio de sesión
            user.last_login_ip = get_client_ip(request)
            user.save(update_fields=['last_login_ip'])
            
            # Redirigir según el tipo de usuario
            if user.is_superuser:
                return redirect('system:admin_dashboard')
            else:
                return redirect('system:dashboard')
        
        return render(request, self.template_name, {
            'title': _('Iniciar Sesión'),
            'form': form
        })


@login_required
def logout_view(request):
    """
    Vista para cerrar sesión.
    """
    logout(request)
    messages.success(request, _('Has cerrado sesión correctamente.'))
    return redirect('system:login')


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Vista del panel principal (dashboard) que se muestra después del login.
    """
    template_name = 'system/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Información básica para el dashboard
        context['title'] = _('Panel Principal')
        
        # Si el usuario tiene empresa, añadir información de módulos disponibles
        if user.company:
            context['company'] = user.company
            context['available_modules'] = self.get_available_modules(user.company)
            
            # Verificar estado de suscripción
            if not user.company.is_subscription_active():
                messages.warning(self.request, _(
                    'La suscripción de tu empresa ha vencido. '
                    'Algunos módulos pueden estar deshabilitados.'
                ))
        
        return context
    
    def get_available_modules(self, company):
        """
        Retorna una lista de módulos disponibles para la empresa
        basado en su configuración.
        """
        modules = []
        
        # Solo añadir módulos si la suscripción está activa
        if company.is_subscription_active():
            if company.module_inventory:
                modules.append({
                    'name': _('Inventario'),
                    'url': '#',  # Se actualizará cuando exista la app
                    'icon': 'fas fa-boxes'
                })
                
            if company.module_sales:
                modules.append({
                    'name': _('Ventas'),
                    'url': '#',  # Se actualizará cuando exista la app
                    'icon': 'fas fa-cash-register'
                })
                
            if company.module_purchases:
                modules.append({
                    'name': _('Compras'),
                    'url': '#',  # Se actualizará cuando exista la app
                    'icon': 'fas fa-shopping-cart'
                })
                
            if company.module_accounting:
                modules.append({
                    'name': _('Contabilidad'),
                    'url': '#',  # Se actualizará cuando exista la app
                    'icon': 'fas fa-calculator'
                })
                
            if company.module_crm:
                modules.append({
                    'name': _('CRM'),
                    'url': '#',  # Se actualizará cuando exista la app
                    'icon': 'fas fa-users'
                })
                
            if company.module_hrm:
                modules.append({
                    'name': _('RRHH'),
                    'url': '#',  # Se actualizará cuando exista la app
                    'icon': 'fas fa-id-card'
                })
        
        return modules


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Vista del panel principal para administradores del sistema.
    """
    template_name = 'system/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Panel de Administración')
        
        # Estadísticas de empresas
        context['total_companies'] = Company.objects.count()
        context['active_companies'] = Company.objects.filter(is_active=True).count()
        context['total_users'] = User.objects.count()
        
        # Empresas recientes
        context['recent_companies'] = Company.objects.all().order_by('-created_at')[:5]
        
        return context


@login_required
def profile_view(request):
    """
    Vista para mostrar y actualizar el perfil del usuario.
    """
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Tu perfil ha sido actualizado correctamente.'))
            return redirect('system:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'system/profile.html', {
        'title': _('Mi Perfil'),
        'form': form
    })


@login_required
def change_password(request):
    """
    Vista para cambiar la contraseña del usuario.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Mantener la sesión activa después del cambio de contraseña
            update_session_auth_hash(request, user)
            messages.success(request, _('Tu contraseña ha sido actualizada correctamente.'))
            return redirect('system:profile')
        else:
            messages.error(request, _('Por favor corrige los errores indicados.'))
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'system/change_password.html', {
        'title': _('Cambiar Contraseña'),
        'form': form
    })


class PasswordResetView(TemplateView):
    """
    Vista para solicitar el restablecimiento de contraseña.
    """
    template_name = 'system/password_reset.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Restablecer Contraseña')
        context['form'] = PasswordResetRequestForm()
        return context
    
    def post(self, request, *args, **kwargs):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                # Aquí se implementaría el envío del correo con el token
                # Por ahora, solo mostramos un mensaje de éxito
                messages.success(request, _(
                    'Se ha enviado un correo con instrucciones para restablecer tu contraseña.'
                ))
                return redirect('system:login')
            except User.DoesNotExist:
                # Por seguridad, no indicamos si el email existe o no
                messages.success(request, _(
                    'Se ha enviado un correo con instrucciones para restablecer tu contraseña.'
                ))
                return redirect('system:login')
        
        return render(request, self.template_name, {
            'title': _('Restablecer Contraseña'),
            'form': form
        })


# --- Vistas de Administración de Usuarios ---

class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vista para listar usuarios (solo para administradores y managers).
    """
    model = User
    template_name = 'system/users/user_list.html'
    context_object_name = 'users'
    paginate_by = 10
    
    def test_func(self):
        # Solo superusers y managers de empresas pueden acceder
        user = self.request.user
        return user.is_superuser or (user.company and user.groups.filter(name='Manager').exists())
    
    def get_queryset(self):
        queryset = User.objects.all()
        user = self.request.user
        
        # Si es manager, solo ver usuarios de su empresa
        if not user.is_superuser and user.company:
            queryset = queryset.filter(company=user.company)
            
        # Búsqueda
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Administración de Usuarios')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Vista para crear un nuevo usuario.
    """
    model = User
    form_class = UserForm
    template_name = 'system/users/user_form.html'
    success_url = reverse_lazy('system:user_list')
    
    def test_func(self):
        # Solo superusers y managers de empresas pueden acceder
        user = self.request.user
        return user.is_superuser or (user.company and user.groups.filter(name='Manager').exists())
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pasar el usuario actual al formulario
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        user = self.request.user
        
        # Si es manager, asignar automáticamente su empresa
        if not user.is_superuser and user.company:
            form.instance.company = user.company
            
            # Verificar límite de usuarios
            if not user.company.can_add_users():
                messages.error(self.request, _(
                    'Has alcanzado el límite máximo de usuarios para tu empresa.'
                ))
                return self.form_invalid(form)
        
        response = super().form_valid(form)
        messages.success(self.request, _('Usuario creado correctamente.'))
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Crear Usuario')
        return context


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Vista para actualizar un usuario existente.
    """
    model = User
    form_class = UserForm
    template_name = 'system/users/user_form.html'
    success_url = reverse_lazy('system:user_list')
    
    def test_func(self):
        # Solo superusers y managers de empresas pueden acceder
        user = self.request.user
        obj = self.get_object()
        
        # Superuser puede editar cualquier usuario
        if user.is_superuser:
            return True
            
        # Manager solo puede editar usuarios de su empresa
        if user.company and user.groups.filter(name='Manager').exists():
            return obj.company == user.company
            
        return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pasar el usuario actual al formulario
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Usuario actualizado correctamente.'))
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Editar Usuario')
        return context


class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Vista para eliminar un usuario.
    """
    model = User
    template_name = 'system/users/user_confirm_delete.html'
    success_url = reverse_lazy('system:user_list')
    
    def test_func(self):
        # Solo superusers y managers de empresas pueden acceder
        user = self.request.user
        obj = self.get_object()
        
        # No permitir auto-eliminación
        if user == obj:
            return False
            
        # Superuser puede eliminar cualquier usuario no superuser
        if user.is_superuser:
            return not obj.is_superuser
            
        # Manager solo puede eliminar usuarios normales de su empresa
        if user.company and user.groups.filter(name='Manager').exists():
            return (obj.company == user.company and 
                    not obj.is_superuser and 
                    not obj.groups.filter(name='Manager').exists())
            
        return False
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Usuario eliminado correctamente.'))
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Eliminar Usuario')
        return context


# --- Vistas de Administración de Empresas (solo superuser) ---

class CompanyListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vista para listar empresas (solo para superusers).
    """
    model = Company
    template_name = 'system/companies/company_list.html'
    context_object_name = 'companies'
    paginate_by = 10
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_queryset(self):
        queryset = Company.objects.all()
        
        # Búsqueda
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(business_name__icontains=search_query) |
                Q(tax_id__icontains=search_query) |
                Q(email__icontains=search_query)
            )
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Administración de Empresas')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class CompanyCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Vista para crear una nueva empresa.
    """
    model = Company
    form_class = CompanyForm
    template_name = 'system/companies/company_form.html'
    success_url = reverse_lazy('system:company_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Empresa creada correctamente.'))
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Crear Empresa')
        return context


class CompanyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Vista para actualizar una empresa existente.
    """
    model = Company
    form_class = CompanyForm
    template_name = 'system/companies/company_form.html'
    success_url = reverse_lazy('system:company_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Empresa actualizada correctamente.'))
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Editar Empresa')
        return context


class CompanyDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Vista para eliminar una empresa.
    """
    model = Company
    template_name = 'system/companies/company_confirm_delete.html'
    success_url = reverse_lazy('system:company_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Empresa eliminada correctamente.'))
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Eliminar Empresa')
        return context


class CompanyDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vista para ver detalles de una empresa y sus usuarios.
    """
    model = Company
    template_name = 'system/companies/company_detail.html'
    context_object_name = 'company'
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.get_object()
        context['title'] = f'{company.name} - {_("Detalles")}'
        context['users'] = company.users.all()
        return context
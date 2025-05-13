from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """
    Modelo que representa una empresa en el sistema.
    Funciona como la puerta de entrada para acceder a todas las herramientas.
    """
    name = models.CharField(_("Nombre"), max_length=100)
    business_name = models.CharField(_("Razón Social"), max_length=150)
    tax_id = models.CharField(_("RUT/ID Fiscal"), max_length=20, unique=True)
    
    # Información de contacto
    address = models.CharField(_("Dirección"), max_length=255, blank=True)
    city = models.CharField(_("Ciudad"), max_length=100, blank=True)
    state = models.CharField(_("Región/Estado"), max_length=100, blank=True)
    country = models.CharField(_("País"), max_length=100, default="Chile")
    postal_code = models.CharField(_("Código Postal"), max_length=20, blank=True)
    phone = models.CharField(_("Teléfono"), max_length=20, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    website = models.URLField(_("Sitio Web"), blank=True)
    
    # Personalización
    logo = models.ImageField(_("Logo"), upload_to="company_logos/", blank=True, null=True)
    primary_color = models.CharField(_("Color Principal"), max_length=7, default="#007bff", 
                                    help_text=_("Código hexadecimal del color, ej: #007bff"))
    
    # Control del sistema
    is_active = models.BooleanField(_("Activo"), default=True)
    max_users = models.PositiveIntegerField(_("Máximo de Usuarios"), default=5)
    subscription_end = models.DateField(_("Fin de Suscripción"), blank=True, null=True)
    
    # Módulos activados (se pueden expandir con más opciones)
    module_inventory = models.BooleanField(_("Módulo Inventario"), default=True)
    module_sales = models.BooleanField(_("Módulo Ventas"), default=True)
    module_purchases = models.BooleanField(_("Módulo Compras"), default=True)
    module_accounting = models.BooleanField(_("Módulo Contabilidad"), default=False)
    module_crm = models.BooleanField(_("Módulo CRM"), default=False)
    module_hrm = models.BooleanField(_("Módulo RRHH"), default=False)
    
    # Metadatos y auditoría
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de Actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Empresa")
        verbose_name_plural = _("Empresas")
        ordering = ["name"]
    
    def __str__(self):
        return self.name
    
    def is_subscription_active(self):
        """Verifica si la suscripción de la empresa está activa"""
        if not self.subscription_end:
            return True
        from django.utils import timezone
        return timezone.now().date() <= self.subscription_end
    
    def get_active_users_count(self):
        """Retorna la cantidad de usuarios activos de la empresa"""
        return self.users.filter(is_active=True).count()
    
    def can_add_users(self):
        """Verifica si la empresa puede añadir más usuarios"""
        return self.get_active_users_count() < self.max_users


class CustomUserManager(BaseUserManager):
    """
    Gestor personalizado de usuarios para permitir el inicio de sesión con email en lugar de username
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El campo Email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Modelo de usuario personalizado que utiliza email como identificador único para autenticación
    en lugar de username.
    """
    username = None  # Removemos el campo username
    email = models.EmailField(_('Correo Electrónico'), unique=True)
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name="users",
        verbose_name=_("Empresa"),
        null=True, blank=True
    )
    phone = models.CharField(_("Teléfono"), max_length=20, blank=True)
    position = models.CharField(_("Cargo"), max_length=100, blank=True)
    profile_picture = models.ImageField(
        _("Imagen de Perfil"), 
        upload_to="profile_pics/", 
        blank=True, 
        null=True
    )
    last_login_ip = models.GenericIPAddressField(_("IP último acceso"), blank=True, null=True)
    
    # Preferencias de usuario
    language_preference = models.CharField(
        _("Idioma Preferido"),
        max_length=10,
        choices=[('es', 'Español'), ('en', 'Inglés')],
        default='es'
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email ya es requerido por ser USERNAME_FIELD
    
    objects = CustomUserManager()
    
    class Meta:
        verbose_name = _("Usuario")
        verbose_name_plural = _("Usuarios")
        
    def save(self, *args, **kwargs):
        # Si el usuario es superuser, no requiere estar asociado a una empresa
        if self.is_superuser:
            self.company = None
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.email
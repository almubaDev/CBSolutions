from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate
from .models import User, Company


class LoginForm(AuthenticationForm):
    """
    Formulario personalizado para inicio de sesión.
    Usa el email en lugar del username.
    """
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('Correo electrónico')}),
        label=_('Correo electrónico')
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': _('Contraseña')}),
        label=_('Contraseña')
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('Recordarme')
    )
    
    error_messages = {
        'invalid_login': _(
            "Por favor ingrese un correo electrónico y contraseña correctos. "
            "Ambos campos pueden ser sensibles a mayúsculas."
        ),
        'inactive': _("Esta cuenta está inactiva."),
    }

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                # Intentar encontrar el usuario para dar mensajes más específicos
                try:
                    user = User.objects.get(email=username)
                    if not user.is_active:
                        raise forms.ValidationError(
                            self.error_messages['inactive'],
                            code='inactive',
                        )
                except User.DoesNotExist:
                    pass
                
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                )
        return self.cleaned_data


class PasswordResetRequestForm(forms.Form):
    """
    Formulario para solicitar restablecimiento de contraseña.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('Correo electrónico')}),
        label=_('Correo electrónico'),
        max_length=254,
        help_text=_('Ingrese el correo electrónico asociado a su cuenta.')
    )


class UserProfileForm(forms.ModelForm):
    """
    Formulario para editar el perfil del usuario.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'position', 'profile_picture', 'language_preference']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'language_preference': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El email no se puede cambiar si ya existe otro usuario con ese email
        if self.instance and self.instance.pk:
            self.fields['email'].widget.attrs['readonly'] = True
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance and self.instance.pk:
            # Si estamos editando un usuario existente, el email no se puede cambiar
            return self.instance.email
        return email


class UserForm(UserCreationForm):
    """
    Formulario para crear y editar usuarios por parte de administradores.
    """
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label=_('Grupos')
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'position', 
                  'company', 'is_active', 'groups', 'profile_picture']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Obtener el usuario actual para aplicar restricciones
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Configurar campo de contraseña como opcional en edición
        if self.instance and self.instance.pk:
            self.fields['password1'].required = False
            self.fields['password1'].help_text = _('Dejar en blanco para mantener la contraseña actual.')
            self.fields['password2'].required = False
            self.fields['password2'].help_text = _('Dejar en blanco para mantener la contraseña actual.')
        
        # Si no es superuser, limitar opciones y permisos
        if self.user and not self.user.is_superuser:
            # Manager solo puede ver su propia empresa
            self.fields['company'].queryset = Company.objects.filter(pk=self.user.company.pk)
            self.fields['company'].widget.attrs['disabled'] = True
            self.fields['company'].required = False
            
            # Manager solo puede asignar grupos no administrativos
            self.fields['groups'].queryset = Group.objects.exclude(name__in=['Admin', 'Administrator'])
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("Las contraseñas no coinciden."))
        return password2
    
    def clean_company(self):
        if self.user and not self.user.is_superuser:
            # Si no es superuser, asignar su propia empresa
            return self.user.company
        return self.cleaned_data.get('company')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Solo establecer contraseña si se proporcionó una nueva
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            # Guardar grupos seleccionados
            self.save_m2m()
        return user


class CompanyForm(forms.ModelForm):
    """
    Formulario para crear y editar empresas.
    """
    class Meta:
        model = Company
        fields = [
            'name', 'business_name', 'tax_id', 'address', 'city', 'state', 
            'country', 'postal_code', 'phone', 'email', 'website', 'logo',
            'primary_color', 'is_active', 'max_users', 'subscription_end',
            'module_inventory', 'module_sales', 'module_purchases', 
            'module_accounting', 'module_crm', 'module_hrm'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'subscription_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'module_inventory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'module_sales': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'module_purchases': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'module_accounting': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'module_crm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'module_hrm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
    def clean_tax_id(self):
        """Validar que el RUT/ID fiscal sea único"""
        tax_id = self.cleaned_data.get('tax_id')
        if Company.objects.filter(tax_id=tax_id).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError(_('Ya existe una empresa con este RUT/ID fiscal.'))
        return tax_id
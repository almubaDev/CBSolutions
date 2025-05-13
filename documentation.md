# Documentación CBSoluciones

## Estructura Actual del Proyecto

### Proyecto: core

El proyecto Django principal se llama "core" y contiene la configuración base y las aplicaciones del sistema.

### Aplicación: system

La aplicación "system" es el módulo central que gestiona la autenticación, usuarios, empresas y permisos en CBSoluciones.

## Modelos Implementados

### Company (Empresa)

**Descripción**: Representa una empresa cliente que utiliza el sistema. Define sus datos básicos y los módulos a los que tiene acceso.

**Campos principales**:
- `name`: Nombre comercial de la empresa
- `business_name`: Razón social de la empresa
- `tax_id`: RUT o identificación fiscal (único)
- `is_active`: Indica si la empresa está activa en el sistema
- `max_users`: Número máximo de usuarios permitidos
- `subscription_end`: Fecha de finalización de la suscripción

**Campos de módulos**:
- `module_inventory`: Acceso al módulo de inventario
- `module_sales`: Acceso al módulo de ventas
- `module_purchases`: Acceso al módulo de compras
- `module_accounting`: Acceso al módulo de contabilidad
- `module_crm`: Acceso al módulo de CRM
- `module_hrm`: Acceso al módulo de RRHH

**Métodos importantes**:
- `is_subscription_active()`: Verifica si la suscripción está vigente
- `get_active_users_count()`: Obtiene la cantidad de usuarios activos
- `can_add_users()`: Verifica si la empresa puede añadir más usuarios

### User (Usuario)

**Descripción**: Modelo personalizado de usuario que reemplaza al modelo predeterminado de Django.

**Características principales**:
- Usa email como identificador único en lugar de username
- Se relaciona con una empresa (excepto superusuarios)

**Campos principales**:
- `email`: Correo electrónico (único, usado para login)
- `company`: Empresa a la que pertenece (ForeignKey a Company)
- `phone`: Número telefónico
- `position`: Cargo en la empresa
- `profile_picture`: Imagen de perfil
- `last_login_ip`: IP del último inicio de sesión
- `language_preference`: Preferencia de idioma

## Vistas Implementadas

### Autenticación

- **LoginView**: Vista personalizada para inicio de sesión con email
- **logout_view**: Vista para cerrar sesión
- **PasswordResetView**: Vista para solicitar restablecimiento de contraseña

### Dashboard

- **DashboardView**: Panel principal para usuarios normales
- **AdminDashboardView**: Panel principal para administradores

### Gestión de Perfil

- **profile_view**: Vista para ver/editar el perfil del usuario
- **change_password**: Vista para cambiar la contraseña

### Administración de Usuarios

- **UserListView**: Listar usuarios (con filtros por permisos)
- **UserCreateView**: Crear nuevos usuarios
- **UserUpdateView**: Editar usuarios existentes
- **UserDeleteView**: Eliminar usuarios (con validaciones)

### Administración de Empresas

- **CompanyListView**: Listar empresas
- **CompanyCreateView**: Crear nuevas empresas
- **CompanyUpdateView**: Editar empresas existentes
- **CompanyDetailView**: Ver detalles de una empresa
- **CompanyDeleteView**: Eliminar empresas

## Formularios

- **LoginForm**: Formulario de inicio de sesión
- **UserProfileForm**: Edición de perfil de usuario
- **UserForm**: Creación/edición de usuarios
- **CompanyForm**: Creación/edición de empresas
- **PasswordResetRequestForm**: Solicitud de restablecimiento de contraseña

## Templates Implementados

### Base y Componentes

- `base.html`: Template base con estructura HTML, menú y pie de página
- Sistema de navegación con:
  - Menú principal
  - Menú de usuario
  - Versión responsive

### Autenticación

- `login.html`: Página de inicio de sesión
- `password_reset.html`: Página para solicitar restablecimiento de contraseña
- `change_password.html`: Formulario para cambiar contraseña

### Dashboard

- `dashboard.html`: Panel principal para usuarios normales
- `admin_dashboard.html`: Panel principal para administradores

### Gestión de Usuario

- `profile.html`: Perfil de usuario
- `users/user_list.html`: Listado de usuarios
- `users/user_form.html`: Formulario de creación/edición
- `users/user_confirm_delete.html`: Confirmación de eliminación

### Gestión de Empresas

- `companies/company_list.html`: Listado de empresas
- `companies/company_form.html`: Formulario de creación/edición
- `companies/company_detail.html`: Vista detallada de empresa
- `companies/company_confirm_delete.html`: Confirmación de eliminación

## Permisos y Seguridad

- Sistema de autenticación basado en email
- Protección de vistas con LoginRequiredMixin
- Control de acceso con UserPassesTestMixin
- Roles diferenciados:
  - Superusuario: Acceso total al sistema
  - Manager: Gestión de usuarios de su empresa
  - Usuario: Acceso a funcionalidades según módulos

## Próximo Módulo: Inventory (Inventario)

### Modelos Planificados

#### Category (Categoría)

**Campos**:
- `name`: Nombre de la categoría
- `description`: Descripción (opcional)
- `company`: Empresa a la que pertenece
- `is_active`: Estado (activo/inactivo)

#### Product (Producto)

**Campos**:
- `name`: Nombre del producto
- `description`: Descripción detallada
- `category`: Categoría a la que pertenece
- `company`: Empresa a la que pertenece
- `sku`: Código interno
- `barcode`: Código de barras
- `cost_price`: Precio de costo
- `selling_price`: Precio de venta
- `stock`: Stock actual
- `min_stock`: Stock mínimo
- `max_stock`: Stock máximo
- `location`: Ubicación física
- `image`: Imagen del producto
- `is_active`: Estado (activo/inactivo)

#### ProductMovement (Movimiento de Producto)

**Campos**:
- `product`: Producto al que se refiere
- `quantity`: Cantidad de movimiento
- `type`: Tipo de movimiento (entrada/salida)
- `reason`: Motivo del movimiento
- `reference`: Referencia (documento, orden, etc.)
- `company`: Empresa a la que pertenece
- `created_by`: Usuario que realizó el movimiento

### Relaciones con System

- Todos los modelos tendrán una relación con `Company` para mantener la separación de datos entre empresas
- Los movimientos de inventario registrarán el usuario que los realizó (relación con `User`)
- El acceso al módulo de inventario estará controlado por el flag `module_inventory` en la empresa
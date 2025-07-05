# HR_Management

# Sistema de Gestión de Reclutamiento y Selección - Premier Automotriz

Este es un sistema web completo desarrollado en Django para gestionar todo el ciclo de vida del reclutamiento y la selección de personal, desde la requisición de una vacante hasta la contratación del candidato.

## 🚀 Características Principales

La aplicación está diseñada con una lógica de negocio robusta y un sistema de permisos detallado para diferentes roles dentro de la empresa.

* **📰 Portal Público de Vacantes:** Una página de inicio donde los candidatos externos pueden ver las oportunidades de carrera disponibles.
* **✍️ Registro de Candidatos Personalizado:** Un formulario de registro completo que permite a los candidatos subir su información, CV, y especificar sus intereses, incluyendo lógica condicional para candidatos internos.
* **🔐 Sistema de Roles y Permisos Granular:** La aplicación maneja múltiples roles, cada uno con su propio dashboard y permisos específicos:
    * **Superusuario:** Control total.
    * **Director:** Aprueba la fase final de las requisiciones.
    * **Gerente General de Marca:** Realiza la primera aprobación de requisiciones, limitado a sus marcas asignadas.
    * **Gerente de Capital Humano:** Asigna vacantes a las asesoras, supervisa todos los procesos y consulta reportes.
    * **Asesora de Reclutamiento:** Gestiona a los candidatos, define perfiles de puesto y actualiza los procesos.
    * **Gerente Operativo:** Crea las solicitudes de nuevas vacantes para su equipo.
* **🔗 Flujo de Aprobación Multinivel:** Las requisiciones de personal deben pasar por una cadena de aprobación (Gerente de Marca -> Director) antes de ser liberadas, asegurando un control presupuestal y estratégico.
* **📚 Biblioteca de Perfiles de Puesto:** Las asesoras definen un perfil detallado para cada vacante (habilidades clave, rasgos, etc.), creando una base de conocimiento reutilizable para futuras contrataciones.
* **📈 Dashboard de Indicadores (KPIs):** Un panel de reportes para la gerencia con indicadores clave de desempeño y tablas interactivas.
* **📜 Historial y Auditoría:** Un registro completo de cada acción importante realizada en el sistema, con la capacidad de filtrar por candidato o usuario.
* **🧠 Lógica de Negocio Inteligente:**
    * Los candidatos rechazados vuelven a la bolsa de trabajo para ser considerados en otros procesos.
    * Se aplican "marcas" visuales a candidatos con historial, con una lógica de expiración de 1 año para los no aprobados en psicometría.

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python 3.11, Django 5.2
* **Frontend:** HTML5, CSS3, JavaScript (con jQuery)
* **Librerías Clave:**
    * `Pillow` para el manejo de imágenes.
    * `mysqlclient` para la conexión con MySQL en producción.
    * `django-jazzmin` para un tema de administración profesional.
    * `DataTables.js` para tablas interactivas.
* **Base de Datos:** SQLite para desarrollo, MySQL para producción.
* **Despliegue:** PythonAnywhere.

## ⚙️ Instalación y Puesta en Marcha Local

Sigue estos pasos para correr el proyecto en tu computadora.

1.  **Clona el repositorio:**
    ```bash
    git clone [https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)
    cd HR_Management
    ```

2.  **Crea y activa un entorno virtual:**
    ```bash
    python -m venv .venv
    # En Windows
    .venv\Scripts\activate
    ```

3.  **Instala las dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Realiza las migraciones de la base de datos:**
    ```bash
    python manage.py migrate
    ```

5.  **Carga el catálogo inicial de puestos (muy importante):**
    ```bash
    python manage.py load_puestos
    ```

6.  **Crea un superusuario** para acceder al panel de administración:
    ```bash
    python manage.py createsuperuser
    ```

7.  **Inicia el servidor de desarrollo:**
    ```bash
    python manage.py runserver
    ```

8.  Accede a la aplicación en `http://127.0.0.1:8000`.

## 📋 Configuración Inicial de Datos

Después de iniciar la aplicación por primera vez, debes configurar los roles y datos iniciales desde el Panel de Administración (`/admin/`).

1.  **Crea los Grupos:** Ve a la sección "Groups" y crea los siguientes grupos (los nombres deben ser exactos):
    * `Asesoras`
    * `Gerentes de Capital Humano`
    * `Gerentes Operativos`
    * `Gerente General de Marca`

2.  **Crea las Marcas:** Ve a la sección "Marcas" y añade las marcas de la empresa (ej. `Chevrolet`, `Nissan`, etc.).

3.  **Crea los Usuarios:** Ve a "Users", crea tus usuarios de prueba y:
    * Asígnalos a su grupo correspondiente.
    * Para los roles de gestión (Director, Gerente General), marca la casilla **"Staff status"**.
    * Baja hasta la sección **"Perfiles de Usuario y Marcas"** y asigna las marcas que cada gerente/director supervisará.
  
    * 1. Filosofía y Arquitectura del Proyecto
Este proyecto es una aplicación web monolítica construida con Django. El objetivo principal es centralizar y gestionar el ciclo de vida completo del reclutamiento de personal, desde la solicitud de una vacante hasta su cierre.

La arquitectura se basa en un Control de Acceso Basado en Roles (RBAC), donde la visibilidad y las acciones de un usuario están estrictamente definidas por su pertenencia a uno o más Grupos de Django.

2. Modelos de Datos Clave (models.py)
La base de datos es el corazón del sistema. Las relaciones entre los modelos son cruciales para entender el flujo de la información.

User (de Django): Es el modelo base para cualquier persona que inicia sesión. No se modifica directamente.

Marca: Un catálogo simple que contiene los nombres de las marcas de la empresa (ej. 'Chevrolet', 'Nissan'). Es gestionable por el Superusuario desde el admin.

PerfilUsuario: Extiende el modelo User. Es el nexo clave para los permisos avanzados.

Tiene una relación OneToOneField con User.

Tiene una relación ManyToManyField con Marca. Aquí es donde se define qué marcas puede gestionar un Director o un Gerente de Marca.

Una señal de Django (ensure_user_profile) se encarga de crear un PerfilUsuario automáticamente cada vez que se crea un nuevo User, asegurando la integridad.

CatalogoPuesto: Un catálogo de los nombres de puestos estandarizados (ej. 'Asesor(a) de ventas', 'Técnico en Diagnóstico'). Gestionable por el Superusuario.

Puesto: Representa una requisición de personal específica. Es el objeto central del flujo de aprobación.

Está conectado vía ForeignKey al CatalogoPuesto (para el nombre estandarizado) y a la Marca.

Contiene toda la información de la solicitud (sueldo, jefe, motivo, etc.).

Maneja el flujo de aprobación con el campo estatus_autorizacion (PENDIENTE -> PENDIENTE_DIR -> AUTORIZADO).

Registra quién y cuándo realizó cada aprobación (aprobado_por_gerente_marca, aprobado_por_director, etc.).

Tiene un campo booleano es_confidencial para manejar vacantes especiales.

PerfilDePuesto: El "expediente" detallado de una requisición, llenado por la asesora.

Tiene una relación OneToOneField con Puesto. Cada requisición tiene un único perfil detallado.

Guarda información cualitativa como habilidades clave, rasgos de personalidad y preguntas sugeridas para la entrevista.

Candidato: Almacena la información de una persona que aplica a la bolsa de trabajo.

Su campo puesto_de_interes es una ForeignKey a Puesto.

Tiene un campo es_colaborador_actual y un motivo_busqueda condicional.

Proceso: Es el modelo que conecta a un Candidato con un Puesto. Representa un único intento de un candidato por una vacante específica.

Un Candidato puede tener muchos Procesos a lo largo del tiempo (si es rechazado y vuelve a aplicar). Esto se logra con una ForeignKey de Proceso a Candidato.

Contiene el estatus_proceso que traza el camino del candidato en el pipeline (psicometría, entrevistas, etc.).

Publicacion: Registra los esfuerzos de marketing para una vacante (posts en redes sociales, con su enlace y monto de inversión). Tiene una ForeignKey a Puesto.

RegistroActividad: La bitácora de auditoría. Es un modelo genérico que registra cada acción importante (creación, aprobación, cambio de estatus) realizada por cualquier usuario.

3. Flujos de Trabajo y Lógica de Vistas (views.py)
3.1. Flujo de Aprobación de Vacantes
Solicitud (portal_gerente_view): Un Gerente Operativo llena el SolicitudPuestoForm. Al guardar, se crea un objeto Puesto con estatus_autorizacion = 'PENDIENTE'. Si un Superusuario marca la casilla es_confidencial, la vacante se aprueba y se abre automáticamente.

Lista de Pendientes (lista_solicitudes_pendientes): Esta vista es inteligente.

Filtra las solicitudes basándose en la marca. Un usuario solo ve las solicitudes de las marcas que tiene asignadas en su PerfilUsuario.

Muestra dos tablas: una para el Gerente de Marca (con estatus PENDIENTE) y otra para el Director (con estatus PENDIENTE_DIR).

Aprobación (aprobar_solicitud): Esta vista es una máquina de estados.

Verifica que el aprobador tenga permiso sobre la marca del puesto.

Si el estatus es PENDIENTE, solo un Gerente de Marca puede actuar. Al aprobar, el estatus cambia a PENDIENTE_DIR.

Si el estatus es PENDIENTE_DIR, solo un Director (is_staff) puede actuar. Al aprobar, el estatus cambia a AUTORIZADO, y el campo esta_abierto se pone en True.

Impide que la misma persona realice las dos aprobaciones consecutivas.

3.2. Flujo de Trabajo de la Asesora
Asignación (asignar_puestos_view): La Gerente de RH ve todos los puestos AUTORIZADOs y los asigna a una Asesora, llenando el campo asesora_encargada.

Lista de Tareas (mis_vacantes_view): La Asesora ve una lista de sus vacantes asignadas que aún no tienen procesos iniciados. Un botón inteligente la guía: si falta el perfil, el botón dice "Definir Perfil"; si ya está definido, dice "Buscar Candidatos".

Definición de Perfil (gestion_perfil_puesto_view): La asesora llena el PerfilDePuestoForm, creando el expediente de la vacante.

Búsqueda de Talento (bolsa_trabajo_view):

Muestra solo candidatos "disponibles" (aquellos que no tienen un proceso activo).

Marca con íconos (⚠️, ℹ️) a los candidatos con historial previo.

Implementa un modo "enfocado": si la asesora llega desde "Mis Vacantes", la página ya sabe para qué puesto está buscando y reemplaza el menú desplegable por un botón de asignación directa.

Gestión del Proceso (detalle_proceso_view): Es el centro de mando. Maneja múltiples acciones (actualizar_estatus, transferir_proceso, add_publication) usando un campo oculto action en los formularios. Es aquí donde se cierra una vacante (puesto.esta_abierto = False) solo cuando un candidato alcanza el estatus final de contratación.

4. Sistema de Permisos
Grupos de Django: Son la base de los roles.

Funciones de Ayuda (es_asesora, etc.): Pequeñas funciones en views.py que centralizan la lógica de "quién es quién". Incluyen al superuser para facilitar las pruebas.

Decoradores (@user_passes_test): Protegen cada vista. Usan el argumento login_url=reverse_lazy('acceso_denegado') para redirigir a una página de error amigable en lugar de al login, mejorando la experiencia de usuario para quienes ya están autenticados.

5. Comandos Personalizados
load_puestos: Un script de gestión (management/commands/) que permite poblar la tabla CatalogoPuesto con una lista predefinida de nombres de puestos, ejecutándose con python manage.py load_puestos.


---
© 2025 Premier Automotriz.

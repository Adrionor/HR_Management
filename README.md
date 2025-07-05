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


---
© 2025 Premier Automotriz.

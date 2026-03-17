# Cool & Go B2B — Sistema de Gestión de Pedidos

> MVP de sistema B2B para la operación logística de Cool & Go, orientado a resolver errores de Pickeo, cumplimiento de reglas FIFO/FEFO y retrasos en la toma de pedidos mediante Inteligencia Artificial.

## 🚀 Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.13 + Django 6 (MVT, DRY) |
| Base de Datos | PostgreSQL (Render) / SQLite (local dev) |
| IA / Backlog | API de Gemini |
| Frontend | TailwindCSS v4 + CSS puro |
| Auth | Django Native Auth + RBAC |
| Deploy | Render.com |

## 🎨 Paleta de Colores

- `primary`: `#1f7ead`
- `secondary`: `#081e2f`
- `accent`: `#b3d9ed`
- `background-light`: `#fafafa`
- `background-dark`: `#14191f`

## 📦 Módulos del MVP

- **Auth B2B** — Login con roles (Admin, Operario, Cliente B2B)
- **Inventario** — Trazabilidad jerárquica: Bodega → Zona → Ubicación → Lote
- **Recepción (Inbound)** — Ingreso de mercancía con control de Lote y Vencimiento
- **Despacho / Picking FEFO** — Motor que asigna siempre el Lote más próximo a vencer
- **Backlog IA** — El cliente B2B pide en lenguaje natural, Gemini convierte a pedido
- **Dashboards** — Lead Time, KPIs de operación, trazabilidad para el cliente

## ⚙️ Instalación Local

```bash
# Clonar el repositorio
git clone https://github.com/CiroCortes/b2b_cool_and_goo.git
cd b2b_cool_and_goo

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tu SECRET_KEY y DATABASE_URL

# Ejecutar migraciones
python manage.py migrate

# Compilar TailwindCSS
python manage.py tailwind build

# Correr el servidor
python manage.py runserver
```

## 📁 Estructura del Proyecto

```
coolgo_b2b_mvp/
├── core/               # Settings, URLs raíz
├── usuarios/           # Auth, Perfil, Roles RBAC
├── inventario/         # Modelos de Stock, Lotes, Ubicaciones
│   └── management/commands/importar_stock_coolgo.py
├── solicitudes/        # Backlog de pedidos B2B + IA
├── despacho/           # Motor FEFO/FIFO + Picking
├── templates/
│   ├── base.html       # Layout maestro (DRY)
│   └── registration/
│       └── login.html
└── theme/              # TailwindCSS
```

## 🔐 Variables de Entorno

Crea un archivo `.env` en la raíz con las siguientes variables:

```env
DEBUG=True
SECRET_KEY='tu-secret-key-aqui'
DATABASE_URL=postgres://usuario:password@host:5432/db_name
GEMINI_API_KEY=tu-api-key-de-gemini
```

---

> Desarrollado con ❤️ sobre la base del motor **sistemaPedidosPesco**.

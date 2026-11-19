# Lista de tareas — Rock del País

Backlog inicial basado en el estado actual del proyecto. Las tareas están agrupadas por especialidad; respetar las dependencias indicadas antes de iniciar trabajo paralelo.

## Prioridad 0 — Alinear y completar gestión de categorías

### Back-end — Luka

- [ ] **BE-01 — Definir el contrato de categoría**  
  Acordar con Walter y el equipo front-end si las categorías tendrán descripción. El modelo actual tiene `name`, `slug`, `active` y `sort_order`; no tiene `description` ni `is_active`.  
  **Aceptación:** los campos que muestra el listado y los que guarda el formulario coinciden con un único contrato documentado.

- [ ] **BE-02 — Completar el listado de categorías**  
  Enviar al template las categorías ordenadas usando los campos reales del modelo.  
  **Aceptación:** la ruta del listado muestra registros reales, su estado activo y el orden establecido.

- [ ] **BE-03 — Corregir rutas de edición y eliminación**  
  Unificar el nombre del argumento de URL (`pk`) con el parámetro esperado por las vistas, o cambiar ambos para que coincidan.  
  **Aceptación:** abrir, guardar y eliminar una categoría funciona sin errores de argumentos.

- [ ] **BE-04 — Proteger las rutas de gestión**  
  Restringir listado, alta, edición y eliminación a usuarios autorizados; conservar los formularios POST y la protección CSRF.  
  **Aceptación:** un usuario no autorizado no puede acceder ni modificar categorías; las acciones válidas muestran mensajes de resultado.

### Front-end — Juan, Emmanuel y Mateo

- [ ] **FE-01 — Alinear la tabla de categorías con el contrato**  
  Actualizar `management_category_list.html`: quitar `description` si no se incorpora al modelo y mostrar el campo `active` en vez de `is_active`.  
  **Aceptación:** el listado no muestra campos inexistentes y contempla estados vacío y con resultados.

- [ ] **FE-02 — Completar estilos del área de gestión**  
  Crear y conectar `manage.css`, que el listado ya intenta cargar; definir tabla, acciones, estados, formularios y adaptación a móvil.  
  **Aceptación:** listado y formulario se ven correctamente en escritorio y móvil, con foco visible y contraste legible.

- [ ] **FE-03 — Mejorar formulario de alta y edición**  
  Aplicar estilos consistentes a errores, ayuda, campos obligatorios, botones y cancelación en `management_category_form.html`.  
  **Aceptación:** los errores de campo y generales son visibles y asociados al formulario; guardar y cancelar son claros.

### DBA — Walter

- [ ] **DB-01 — Revisar esquema y migraciones de categorías**  
  Confirmar el esquema desplegado frente al modelo y las migraciones. Revisar la decisión del campo `description` antes de proponer una migración.  
  **Aceptación:** se documenta si hace falta una migración; si la hay, se prueba sin pérdida de datos.

## Prioridad 1 — Tienda y catálogo

### Front-end

- [ ] **FE-04 — Diseñar la página principal de la tienda** — Emmanuel  
  Reemplazar el contenido provisional de `home.html` con una portada de tienda coherente con la identidad visual existente.  
  **Aceptación:** jerarquía clara, navegación a productos y presentación adaptable a móvil.

- [ ] **FE-05 — Crear catálogo y filtros** — Juan  
  Diseñar listado de productos, estados sin resultados, precio, stock y navegación por categoría.  
  **Aceptación:** cada producto enlaza a su detalle y la interfaz comunica claramente disponibilidad.

- [ ] **FE-06 — Crear detalle de producto y agregar al carrito** — Mateo  
  Presentar imágenes, descripción, precio, stock y selección de cantidad.  
  **Aceptación:** cantidad inválida o superior al stock se informa sin confundir al usuario.

- [ ] **FE-07 — Crear vistas de carrito y checkout** — Mateo  
  Diseñar resumen, edición de cantidades, datos de contacto y selección de los medios de pago ya definidos (transferencia o efectivo al retirar).  
  **Aceptación:** totales y errores de validación son visibles antes de confirmar el pedido.

### Back-end — Luka

- [ ] **BE-05 — Publicar catálogo desde la portada**  
  Consultar categorías activas y productos publicados; completar el contexto de la página principal.  
  **Aceptación:** productos inactivos y categorías inactivas no aparecen en la tienda pública.

- [ ] **BE-06 — Implementar catálogo, detalle y búsqueda básica**  
  Agregar rutas y vistas para filtrar productos por categoría y consultar un producto publicado.  
  **Aceptación:** URLs y estados inexistentes se manejan correctamente; consultas usan datos reales.

- [ ] **BE-07 — Implementar carrito persistente por sesión**  
  Validar producto, cantidad y stock al agregar, actualizar o quitar artículos.  
  **Aceptación:** el subtotal se recalcula en el servidor y no se aceptan cantidades inválidas.

- [ ] **BE-08 — Implementar creación y seguimiento de pedidos**  
  Validar checkout, registrar pedido e ítems con precios de compra y reservar/actualizar stock de manera transaccional.  
  **Aceptación:** el stock no queda negativo; si una operación falla, no se guarda un pedido parcial.

### DBA — Walter

- [ ] **DB-02 — Validar datos y concurrencia de inventario**  
  Revisar restricciones de stock, precios, claves foráneas e índices necesarios para catálogo y pedidos.  
  **Aceptación:** recomendaciones documentadas y cambios de esquema coordinados con Luka mediante migraciones.

- [ ] **DB-03 — Preparar datos de prueba**  
  Definir un conjunto reproducible de categorías y productos de prueba, sin datos personales reales.  
  **Aceptación:** el equipo puede probar catálogo y checkout de forma repetible en un entorno no productivo.

## Prioridad 2 — Cuenta, consultas y operación

### Front-end — Juan (responsable), Emmanuel y Mateo (revisión)

- [ ] **FE-08 — Crear pantallas de registro e inicio de sesión**  
  Conectar la navegación actual con pantallas y estados de autenticación reales.  
  **Aceptación:** formularios accesibles, errores entendibles y navegación posterior al acceso.

- [ ] **FE-09 — Crear panel de gestión de productos y pedidos**  
  Reutilizar patrones del área de categorías para formularios, estados y acciones de gestión.  
  **Aceptación:** la interfaz distingue claramente acciones de gestión y estados de pedidos.

- [ ] **FE-10 — Crear formulario y confirmación de consultas**  
  Añadir una pantalla de contacto conectada desde navegación y pie de página.  
  **Aceptación:** se muestran validaciones y confirmación tras el envío.

### Back-end — Luka

- [ ] **BE-09 — Completar autenticación y permisos de gestión**  
  Conectar registro, acceso y salida con las vistas y rutas reales.  
  **Aceptación:** permisos y redirecciones funcionan tanto para usuarios anónimos como autenticados.

- [ ] **BE-10 — Implementar gestión de productos y pedidos**  
  Incorporar listados y operaciones de gestión utilizando los formularios y modelos existentes.  
  **Aceptación:** operaciones restringidas al personal autorizado y con validación en servidor.

- [ ] **BE-11 — Implementar recepción y gestión de consultas**  
  Guardar consultas validadas y permitir su revisión por personal autorizado.  
  **Aceptación:** el visitante recibe confirmación y el equipo puede identificar consultas respondidas.

### DBA — Walter

- [ ] **DB-04 — Definir respaldo y recuperación de la base**  
  Documentar frecuencia, retención y procedimiento de restauración para MySQL según el entorno de despliegue.  
  **Aceptación:** restauración probada en un entorno seguro, sin incluir credenciales en el repositorio.

## Validación compartida

- [ ] **QA-01 — Agregar pruebas para flujos prioritarios** — Luka + revisión de Emmanuel, Juan y Mateo  
  Cubrir CRUD de categorías, visibilidad del catálogo, validación de stock y creación de pedidos.  
  **Aceptación:** `manage.py test` ejecuta pruebas automatizadas con datos aislados.

- [ ] **QA-02 — Revisar responsive, accesibilidad y errores** — Emmanuel, Juan y Mateo  
  Probar navegación por teclado, pantallas móviles, mensajes, formularios y estados vacíos.  
  **Aceptación:** checklist de revisión completado antes de publicar cada flujo.

## Secuencia recomendada

1. **BE-01 + DB-01**: acordar contrato y esquema de categorías.
2. **BE-02 + BE-03**: completar listado y rutas.
3. **FE-01 + FE-02 + FE-03**: cerrar la interfaz de gestión de categorías.
4. **BE-04 + QA-01**: proteger rutas y probar el flujo.
5. Continuar con Prioridad 1 y luego Prioridad 2, respetando dependencias entre interfaz, API/vistas y esquema.

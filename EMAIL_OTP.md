# Verificación por correo

El inicio de sesión de la tienda y del administrador requiere contraseña y un código enviado por correo. El registro también exige verificar el correo antes de iniciar sesión. Las sesiones autenticadas anteriores deben iniciar sesión nuevamente.

## Configuración

1. Activá la verificación en dos pasos de la cuenta de Google y generá una contraseña de aplicación para Gmail, si tu cuenta lo permite.
2. Configurá `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL` como variables de entorno del proceso. Usá la dirección de Gmail como usuario y remitente; `EMAIL_HOST_PASSWORD` debe ser la contraseña de aplicación, no la contraseña habitual. **No guardes credenciales en `.env`: este archivo está versionado en el repositorio.** No compartas ni subas estas credenciales.
3. Aplicá las migraciones con `python manage.py migrate` y reiniciá Django.
4. Verificá que todas las cuentas existentes, incluidas las de personal, tengan una dirección de correo válida. Las cuentas sin correo no pueden ingresar; un administrador debe actualizar su dirección mediante un canal seguro.

Los códigos vencen en diez minutos, admiten cinco intentos y el reenvío está limitado a uno por minuto. Solicitar otro código invalida el anterior. Si el envío falla luego del registro, la cuenta permanece creada y puede volver a iniciar sesión cuando el correo esté disponible.

La configuración actual acepta cualquier subdominio de `trycloudflare.com` como host y origen CSRF. Para una instalación expuesta, reemplazá esos comodines por el hostname y origen HTTPS específicos del túnel controlado por el equipo, y configurá HTTPS y cookies seguras. El correo electrónico como segundo factor depende de la seguridad del buzón y no protege contra phishing como lo haría una llave de seguridad.

# Publicar el proyecto en GitHub

Para la evidencia local no se necesita cuenta de GCP ni de AWS. Sí se necesita una cuenta de GitHub para crear el repositorio propio.

1. En GitHub, crear un repositorio vacío, por ejemplo `otel-observability-lab`. No agregar README, `.gitignore` ni licencia desde la página, porque ya existen localmente.
2. En PowerShell, desde `C:\Users\User\Desktop\otel-observability-lab`, revisar que no haya secretos:

```powershell
git status
git grep -n -i "password\|secret\|token\|access_key" -- ':!*.md'
```

Los valores `app_password` y `admin/admin` son credenciales locales de demostración, no credenciales cloud. Si la institución exige no publicarlas, reemplazarlas por variables antes del push.

3. Crear el primer commit:

```powershell
git add .
git commit -m "feat: add local OpenTelemetry observability lab"
```

4. Asociar la URL del repositorio propio y publicar:

```powershell
git branch -M main
git remote add origin https://github.com/TU_USUARIO/otel-observability-lab.git
git push -u origin main
```

No compartir tokens de GitHub en el README ni en el reporte. Si Git solicita autenticación, usar el flujo de navegador o un Personal Access Token administrado por GitHub Credential Manager.

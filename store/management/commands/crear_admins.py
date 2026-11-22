from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Crea los 5 superusuarios del equipo en la base de datos"

    def handle(self, *args, **kwargs):
        superusuarios = [
            ("Emma7689", "delorenzoemmanuel@gmail.com" , "gael2022"),
            ("admin2", "admin2@ejemplo.com", "ClaveSegura123!"),
            ("admin3", "admin3@ejemplo.com", "ClaveSegura123!"),
            ("admin4", "admin4@ejemplo.com", "ClaveSegura123!"),
            ("admin5", "admin5@ejemplo.com", "ClaveSegura123!"),
        ]

        for username, email, password in superusuarios:
            if not User.objects.filter(username=username).exists():
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                )
                self.stdout.write(self.style.SUCCESS(f"Superusuario creado: {username}"))
            else:
                self.stdout.write(f"Ya existía: {username}")
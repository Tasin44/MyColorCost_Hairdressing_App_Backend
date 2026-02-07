from django.apps import AppConfig


class AppointmentappConfig(AppConfig):
    name = 'appointmentapp'

def ready(self):
    import appointmentapp.signals  # ✅ Import signals
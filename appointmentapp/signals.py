#Create appointmentapp/signals.py:
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Appointment

@receiver(post_save, sender=Appointment)
def update_client_next_appointment(sender, instance, created, **kwargs):
    """Update client's next appointment date after creating/updating appointment"""
    if instance.client and instance.status == 'scheduled':
        # Find next scheduled appointment for this client
        next_appt = Appointment.objects.filter(
            client=instance.client,
            status='scheduled',
            appointment_date__gte=timezone.now().date()
        ).order_by('appointment_date', 'appointment_time').first()
        
        if next_appt:
            instance.client.next_appointment_date = next_appt.appointment_date
            instance.client.save(update_fields=['next_appointment_date'])

@receiver(post_delete, sender=Appointment)
def update_client_next_appointment_on_delete(sender, instance, **kwargs):
    """Update client's next appointment when appointment is deleted"""
    if instance.client:
        next_appt = Appointment.objects.filter(
            client=instance.client,
            status='scheduled',
            appointment_date__gte=timezone.now().date()
        ).order_by('appointment_date', 'appointment_time').first()
        
        if next_appt:
            instance.client.next_appointment_date = next_appt.appointment_date
        else:
            instance.client.next_appointment_date = None
        instance.client.save(update_fields=['next_appointment_date'])



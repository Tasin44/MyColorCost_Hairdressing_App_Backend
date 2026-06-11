from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from authapp.models import User
from clientapp.models import Client
from appointmentapp.models import ServiceType, DailyWorkingHours, AppointmentURL, Appointment, TimeSlotBooking
from datetime import date, time

class NewAppointmentAPITests(APITestCase):

    def setUp(self):
        # Create an owner user
        self.owner = User.objects.create_user(
            username="owner_user",
            email="owner@example.com",
            password="testpassword123",
            role="owner"
        )
        # Create a client
        self.client_obj = Client.objects.create(
            user=self.owner,
            name="Test Client",
            email="client@example.com"
        )
        # Generate AppointmentURL
        self.appt_url = AppointmentURL.objects.create(
            user=self.owner,
            token="test-token-123"
        )

    def test_service_crud_operations(self):
        self.client.force_authenticate(user=self.owner)

        # 1. Create a service
        create_url = reverse("appointment:service-list")
        data = {
            "name": "Spa",
            "description": "A very relaxing spa experience",
            "service_time_minutes": 30,
            "price_type": "fixed",
            "service_fee": "5.00"
        }
        response = self.client.post(create_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["name"], "Spa")
        service_id = response.data["data"]["id"]

        # 2. Get services list
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["total_count"], 1)

        # 3. Get service detail
        detail_url = reverse("appointment:service-detail", args=[service_id])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["description"], "A very relaxing spa experience")

        # 4. Patch service
        patch_data = {"description": "Updated spa experience"}
        response = self.client.patch(detail_url, patch_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["description"], "Updated spa experience")

        # 5. Delete service
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ServiceType.objects.filter(id=service_id).exists())

    def test_daily_working_hours_setup(self):
        self.client.force_authenticate(user=self.owner)

        setup_url = reverse("appointment:new-working-hours-setup")
        # POST/setup daily working hours
        data = {
            "days": [
                {"weekday": 0, "start_time": "09:00", "end_time": "17:00", "is_off": False},
                {"weekday": 1, "start_time": "09:00", "end_time": "17:00", "is_off": False},
                {"weekday": 6, "is_off": True}
            ]
        }
        response = self.client.post(setup_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DailyWorkingHours.objects.filter(user=self.owner).count(), 3)

        # GET daily working hours
        response = self.client.get(setup_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["working_days"]), 3)

        # PATCH daily working hours
        patch_data = {
            "days": [
                {"weekday": 1, "is_off": True}
            ]
        }
        response = self.client.patch(setup_url, patch_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(DailyWorkingHours.objects.get(user=self.owner, weekday=1).is_off)

    def test_new_appointment_creation_and_slots(self):
        self.client.force_authenticate(user=self.owner)

        # Setup working hours first
        setup_url = reverse("appointment:new-working-hours-setup")
        data = {
            "days": [
                {"weekday": 0, "start_time": "09:00", "end_time": "17:00", "is_off": False}
            ]
        }
        self.client.post(setup_url, data, format="json")

        # Create services
        service = ServiceType.objects.create(
            user=self.owner,
            name="Hair Cut",
            service_time_minutes=30,
            price_type="fixed",
            service_fee="15.00"
        )
        service2 = ServiceType.objects.create(
            user=self.owner,
            name="Beard Trim",
            service_time_minutes=15,
            price_type="fixed",
            service_fee="10.00"
        )

        # 1. Check available slots
        # Let's pick a Monday (e.g. 2026-06-15 is a Monday)
        slots_url = reverse("appointment:new-available-slots")
        response = self.client.get(slots_url, {"date": "2026-06-15"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["is_working_day"])
        self.assertGreater(len(response.data["data"]["available_slots"]), 0)

        # 2. Create appointment
        create_url = reverse("appointment:new-appointment-create")
        appt_data = {
            "client_id": self.client_obj.id,
            "appointment_date": "2026-06-15",
            "appointment_time": "10:00",
            "service_type_ids": [service.id, service2.id],
            "processing_time": 10,
            "blocked_time": 5,
            "extra_servicing": 15
        }
        response = self.client.post(create_url, appt_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["processing_time"], 10)
        self.assertEqual(response.data["data"]["blocked_time"], 5)
        self.assertEqual(response.data["data"]["extra_servicing"], 15)
        self.assertEqual(response.data["data"]["service_display"], "Beard Trim, Hair Cut")
        self.assertEqual(len(response.data["data"]["services"]), 2)

    def test_new_self_booking(self):
        # Setup working hours first for owner
        DailyWorkingHours.objects.create(
            user=self.owner,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_off=False
        )

        # Create service
        service = ServiceType.objects.create(
            user=self.owner,
            name="Spa",
            service_time_minutes=30,
            price_type="fixed",
            service_fee="25.00"
        )

        # 1. GET self booking page data (without auth)
        self_booking_url = reverse("appointment:new-self-booking", args=[self.appt_url.token])
        response = self.client.get(self_booking_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["salon_name"], "owner@example.com")
        self.assertEqual(len(response.data["data"]["services"]), 1)

        # 2. POST self booking (without auth)
        booking_data = {
            "client_name": "New Client Guest",
            "client_contact": "1234567890",
            "client_email": "guest@example.com",
            "appointment_date": "2026-06-15",
            "appointment_time": "11:00",
            "service_type_id": service.id
        }
        response = self.client.post(self_booking_url, booking_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["client_name"], "New Client Guest")
        self.assertEqual(response.data["data"]["appointment_type"], "self_booked")

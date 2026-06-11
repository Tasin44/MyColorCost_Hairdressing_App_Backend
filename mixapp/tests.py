from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from authapp.models import User
from clientapp.models import Client
from appointmentapp.models import ServiceType
from mixapp.models import ShopProduct, UserProduct, Mix, Bowl, BowlProduct
from decimal import Decimal

class NewMixAPITests(APITestCase):

    def setUp(self):
        # Create owner
        self.owner = User.objects.create_user(
            username="owner_user",
            email="owner@example.com",
            password="testpassword123",
            role="owner"
        )
        # Create client
        self.client_obj = Client.objects.create(
            user=self.owner,
            name="Mix Test Client",
            email="mixtest@example.com"
        )
        # Create ServiceType
        self.service = ServiceType.objects.create(
            user=self.owner,
            name="Hair Coloring Service",
            service_time_minutes=45,
            price_type="fixed",
            service_fee="50.00"
        )
        # Create ShopProduct
        self.shop_product = ShopProduct.objects.create(
            name="Super Color Dye",
            market_price=Decimal("15.00"),
            barcode="1234567890123"
        )
        # Create UserProduct
        self.user_product = UserProduct.objects.create(
            user=self.owner,
            product=self.shop_product,
            user_price=Decimal("12.00"),
            current_weight_grams=Decimal("200.00"),
            original_weight_grams=Decimal("200.00"),
            is_available=True
        )

    def test_create_mix_with_bowls(self):
        self.client.force_authenticate(user=self.owner)

        create_url = reverse("mixapp:new-mix-create-list")
        mix_data = {
            "client_id": self.client_obj.id,
            "service_type": str(self.service.id),
            "bowls": [
                {
                    "service_name": "Hair Coloring Service",
                    "mix_name": "Bowl 1 Mix",
                    "charged_amount": "80.00",
                    "bleach_timer_start_time": "2026-06-09T12:00:00",
                    "products": [
                        {
                            "user_product_id": self.user_product.id,
                            "used_weight": "50.00",
                            "user_price": "12.00",
                            "market_price": "15.00"
                        }
                    ]
                }
            ]
        }
        # Create Mix
        response = self.client.post(create_url, mix_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["service_type_info"]["id"], self.service.id)
        self.assertEqual(len(response.data["data"]["bowls"]), 1)
        mix_id = response.data["data"]["id"]

        # Check that product weight was reduced
        self.user_product.refresh_from_db()
        self.assertEqual(self.user_product.current_weight_grams, Decimal("150.00"))

        # List Mixes
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["total_count"], 1)

        # Get Mix Detail
        detail_url = reverse("mixapp:new-mix-detail", args=[mix_id])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["bowls"]), 1)
        self.assertEqual(response.data["data"]["bowls"][0]["mix_name"], "Bowl 1 Mix")

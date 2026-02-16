from django.contrib import admin

# Register your models here.
# Register your models here.
from .models import ReferralCode,Referral,Subscription,CommissionWithdrawal

# Register your models here.
admin.site.register(ReferralCode)
admin.site.register(Referral)
admin.site.register(CommissionWithdrawal)


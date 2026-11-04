from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Order


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="Электронная почта")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class CheckoutForm(forms.ModelForm):
    consent = forms.BooleanField(
        label="Соглашаюсь с условиями оферты и политикой обработки персональных данных"
    )

    class Meta:
        model = Order
        fields = ["full_name", "email", "phone", "delivery", "address", "comment"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_full_name(self):
        value = self.cleaned_data["full_name"].strip()
        if len(value.split()) < 3:
            raise forms.ValidationError("Укажите фамилию, имя и отчество полностью.")
        return value

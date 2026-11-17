from django import forms
from django.urls import reverse

from .models import Banner, News, ProductImage


class BannerAdminForm(forms.ModelForm):
    product_image_id = forms.CharField(required=False, widget=forms.HiddenInput)
    news_image_id = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Banner
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].required = False
        self.fields['product_image_id'].widget.attrs['data-banner-source-url'] = reverse('admin:shop_banner_source')

    def clean(self):
        cleaned = super().clean()
        product_image_id = cleaned.get('product_image_id')
        news_image_id = cleaned.get('news_image_id')
        product = cleaned.get('product')
        news = cleaned.get('news')
        if product_image_id and news_image_id:
            raise forms.ValidationError('Выберите один источник изображения.')
        if product_image_id:
            photo = ProductImage.objects.filter(pk=product_image_id, product=product).first() if product and product_image_id.isdigit() else None
            if not photo or not photo.image:
                self.add_error('product_image_id', 'Выберите фотографию выбранного товара.')
            else:
                cleaned['image'] = photo.image
        elif news_image_id:
            source = News.objects.filter(pk=news_image_id).first() if news and news_image_id.isdigit() and str(news.pk) == news_image_id else None
            if not source or not source.image:
                self.add_error('news_image_id', 'У выбранной новости нет изображения.')
            else:
                cleaned['image'] = source.image
        if not cleaned.get('image'):
            self.add_error('image', 'Загрузите изображение или выберите фотографию товара либо новости.')
        return cleaned

from django.db import migrations


def create_initial_banners(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    ProductImage = apps.get_model('shop', 'ProductImage')
    Banner = apps.get_model('shop', 'Banner')
    for position, product in enumerate(Product.objects.filter(active=True, featured=True).order_by('title')[:3]):
        photo = ProductImage.objects.filter(product_id=product.pk).order_by('position', 'pk').first()
        if photo and photo.image:
            Banner.objects.create(title=product.title, subtitle=' · '.join(filter(None, [product.sku, product.scale])), image=photo.image.name, image_alt=product.title, product_id=product.pk, position=position)


class Migration(migrations.Migration):
    dependencies = [('shop', '0004_news_banner')]
    operations = [migrations.RunPython(create_initial_banners, migrations.RunPython.noop)]

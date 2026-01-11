

from django.db import migrations, models
import django.core.validators
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('location', models.CharField(max_length=100)),
                ('property_type', models.CharField(choices=[('house', 'House'), ('apartment', 'Apartment'), ('condo', 'Condo'), ('townhouse', 'Townhouse'), ('villa', 'Villa'), ('cabin', 'Cabin'), ('studio', 'Studio'), ('loft', 'Loft')], default='house', max_length=20)),
                ('bedrooms', models.PositiveIntegerField(default=1, validators=[django.core.validators.MaxValueValidator(20)])),
                ('bathrooms', models.PositiveIntegerField(default=1, validators=[django.core.validators.MaxValueValidator(20)])),
                ('square_feet', models.PositiveIntegerField(blank=True, null=True)),
                ('is_available', models.BooleanField(default=True)),
                ('featured', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'properties',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['price'], name='properties_price_1234_idx'),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['location'], name='properties_locatio_abcd_idx'),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['property_type'], name='properties_propert_5678_idx'),
        ),
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['created_at'], name='properties_created_efgh_idx'),
        ),
    ]

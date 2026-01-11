from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class Property(models.Model):
    PROPERTY_TYPES = [
        ('house', 'House'),
        ('apartment', 'Apartment'),
        ('condo', 'Condo'),
        ('townhouse', 'Townhouse'),
        ('villa', 'Villa'),
        ('cabin', 'Cabin'),
        ('studio', 'Studio'),
        ('loft', 'Loft'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    location = models.CharField(max_length=100)
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='house')
    bedrooms = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(20)])
    bathrooms = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(20)])
    square_feet = models.PositiveIntegerField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'properties'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['price']),
            models.Index(fields=['location']),
            models.Index(fields=['property_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.location}"
    
    @property
    def price_per_sqft(self):
        """Calculate price per square foot"""
        if self.square_feet and self.square_feet > 0:
            return self.price / self.square_feet
        return None
    
    @property
    def short_description(self):
        """Get first 100 characters of description"""
        return self.description[:100] + '...' if len(self.description) > 100 else self.description

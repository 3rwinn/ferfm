from django.db import models

class Actu(models.Model):
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Actu object (id: {self.id})" 
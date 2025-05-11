from django.db import migrations

def create_allergens(apps, schema_editor):
    Allergen = apps.get_model('recipes', 'Allergen')
    allergens = [
        ("Cereals (Wheat, Rye, Barley, Oats)", "Gluten-containing cereals and their products."),
        ("Crustaceans (Prawns, Crabs, Lobster)", "All types of shellfish."),
        ("Eggs", "Chicken, duck, and other eggs."),
        ("Fish", "All types of fish."),
        ("Lupin", "Lupin and products thereof."),
        ("Milk", "Milk and dairy products."),
        ("Molluscs (Mussels, Oysters, etc.)", "All types of molluscs."),
        ("Mustard", "Mustard and products thereof."),
        ("Peanuts", "Peanuts and products thereof."),
        ("Sesame", "Sesame seeds and products thereof."),
        ("Soybeans", "Soybeans and products thereof."),
        ("Sulphur Dioxide and Sulphites", "Often used as preservatives."),
        ("Tree Nuts (Almonds, Walnuts, Cashews, etc.)", "All types of tree nuts."),
        ("Celery", "Celery and products thereof."),
    ]
    for name, description in allergens:
        Allergen.objects.get_or_create(name=name, defaults={'description': description})

def reverse_func(apps, schema_editor):
    Allergen = apps.get_model('recipes', 'Allergen')
    Allergen.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('recipes', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(create_allergens, reverse_func),
    ] 
from app.models import Category, Text


def get_categories():
    return Category.query.all()

def get_geolocation():
    return Text.query.filter_by(title='geolocation').first()
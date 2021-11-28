from app.models import Category


def get_categories():
    return Category.query.all()

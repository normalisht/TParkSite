from app.models import Category, Text


def get_categories():
    return Category.query.all()


def get_geolocation():
    return Text.query.filter_by(title='geolocation').first()


def get_address():
    return Text.query.filter_by(title='address').first()


def get_phone_numbers():
    return Text.query.filter_by(title='phone_numbers').first().text.split()


def get_media():
    return [Text.query.filter_by(title='vk').first(),
            Text.query.filter_by(title='insta').first()]


def get_contacts_data():
    return {
        'geolocation': get_geolocation(),
        'address': get_address(),
        'phone_numbers': get_phone_numbers(),
        'media': get_media()
    }

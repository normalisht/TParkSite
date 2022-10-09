from flask import flash
from app.models import Category, Text
import os
from app import db
from PIL import Image

def get_categories():
    return Category.query.order_by(Category.number).all()


def get_geolocation():
    return Text.query.filter_by(title='geolocation').first()


def get_address():
    return Text.query.filter_by(title='address').first()


def get_phone_numbers():
    return Text.query.filter_by(title='phone_numbers').first().text.split()


def get_media():
    return [Text.query.filter_by(title='vk').first(),
            Text.query.filter_by(title='insta').first()]


def saving_changes(request, project, project_number):
    changes = False
    result = request.form

    if request.files['logo']:
        photo = request.files['photo']
        photo.save(os.path.join('app/static/images/{}'.format(project_number), 'photo.png'))
        changes = True

    db.session.commit()
    if changes:
        flash('Изменения сохранены', 'success')


def get_contacts_data():
    return {
        'geolocation': get_geolocation(),
        'address': get_address(),
        'phone_numbers': get_phone_numbers(),
        'media': get_media()
    }


def compress (width, height, path_to_file):
    foo = Image.open(path_to_file)
    foo = foo.resize((width,height), Image.ANTIALIAS)
    foo.save(path_to_file, optimize=True,quality=95)
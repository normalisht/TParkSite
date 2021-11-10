from datetime import datetime
from enum import unique
from time import time
from flask import current_app
from sqlalchemy import event, DDL
from app import db, login
from flask_login import UserMixin


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    price = db.Column(db.Integer)
    short_description = db.Column(db.String(512))  # краткое описание
    description = db.Column(db.Text)  # полное описание
    number = db.Column(db.Integer, index=True)  # порядковый номер
    status = db.Column(db.BOOLEAN())  # on/off
    categories = db.relationship('ServiceCategory', backref='service', lazy='dynamic')


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    description = db.Column(db.Text)
    status = db.Column(db.BOOLEAN())  # on/off
    number = db.Column(db.Integer, index=True)  # порядковый номер
    services = db.relationship('ServiceCategory', backref='category', lazy='dynamic')


class ServiceCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    service_id = db.Column(db.ForeignKey('service.id'))
    category_id = db.Column(db.ForeignKey('category.id'))


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    photo = db.Column(db.String(1024))
    name = db.Column(db.String(128))
    position = db.Column(db.String(64))  # должность


class Text(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    title = db.Column(db.String(64), unique=True)  # название текста
    text = db.Column(db.Text)  # содержание


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))  # имя комментатора
    text = db.Column(db.Text)  # содержание


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    email = db.Column(db.String(128))
    password = db.Column(db.String(64))

    def check_password(self, password):
        return self.password == password


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    date = db.Column(db.Date)
    link = db.Column(db.String(1024))  # ссылка на мероприятие(соц сеть или левый сайт)
    description = db.Column(db.Text)

    def check_date(self):
        """Если дата мероприятия прошла, оно удаляется"""
        if self.date < datetime.now():
            db.session.delete(self)
            db.session.commit()


@login.user_loader
def load_user(id):
    return Admin.query.get(int(id))


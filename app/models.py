from datetime import datetime
from enum import unique
from time import time
from flask import current_app
from sqlalchemy import event, DDL
from app import db


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    price = db.Column(db.Integer)
    number = db.Column(db.Integer, index=True)  # порядковый номер
    category = db.Column(db.String(64))
    status = db.Column(db.BOOLEAN())  # on/off


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    status = db.Column(db.BOOLEAN())  # on/off


class Personal(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    photo = db.Column(db.String(1024))
    name = db.Column(db.String(128))
    position = db.Column(db.String(64))  # должность


class Text(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    title = db.Column(db.String(64))  # название текста
    text = db.Column(db.Text)  # содержание


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    text = db.Column(db.Text)

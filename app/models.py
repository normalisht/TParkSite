from datetime import datetime
from enum import unique
from time import time
from flask import current_app
from sqlalchemy import event, DDL
from app import db


class Services(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    name = db.Column(db.String(128))
    price = db.Column(db.Integer)


class Personal(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    photo = db.Column(db.String(1024))
    name = db.Column(db.String(128))
    position = db.Column(db.String(64))


class Texts(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    title = db.Column(db.String(64))
    text = db.Column(db.Text)


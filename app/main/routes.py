from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from typing import List

from app.main import bp
from app import db
import os
import datetime
import time
from os import listdir
from app.models import Text, Comment, Event, Category, ServiceCategory, Service, Employee, Partner, Price
from app.main.functions import get_categories, get_contacts_data, compress
from sqlalchemy import create_engine
from flask_ckeditor import CKEditor
import shutil

engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():
    main_text = Text.query.filter_by(title="main_text").first().text
    events = Event.query.order_by(Event.date).all()
    events_2 = []
    slider_events = True
    len_slider = len(os.listdir('app/static/images/staff'))

    for event in events:
        date = datetime.date(int(event.date.strftime('%Y')), int(event.date.strftime('%m')), int(event.date.strftime('%d')))
        dt = datetime.datetime.combine(date, datetime.time(22, 0))

        if dt > datetime.datetime.now():
            events_2.append(event)

    if len(events_2) == 0:
        slider_events = False
    elif len(events_2) < 3:
        events_2 = events_2 * 3

    return render_template('main/main.html', main_text=main_text, events=events_2[1:] + events_2[:1],
                           categories=get_categories(), contacts_data=get_contacts_data(),
                           len_slider=len_slider, slider_events=slider_events)


@bp.route('/category', methods=['GET'])
def category():
    try:
        category_id = request.args.get('category_id')
        try:
            os.chdir('app/static/images/category/{}'.format(category_id))
            temp = os.getcwd()
            files = listdir(temp)
            path = os.path.join(os.getcwd(), files[0])
            open(path)
            a = 1
            os.chdir('../../../../../')
        except:
            a = 0
            files = []
        category = Category.query.filter_by(id=category_id).first()
        services = category.services.order_by(ServiceCategory.number).all()

        if category.status == 1:
            return render_template('main/category.html', category=category, category_id=category_id,
                                   services=services, categories=get_categories(),
                                   contacts_data=get_contacts_data(), a=a, files=files)
        else:
            return redirect(url_for('main.index'))
    except:
        return render_template('errors/500.html')


@bp.route('/category/service', methods=['GET'])
def service():
    service_id = request.args.get('service_id')

    service = Service.query.filter_by(id=service_id).first()

    return render_template('main/service.html', service=service, categories=get_categories(),
                           files=os.path.isfile('app/static/images/service/{}.png'.format(service_id)),
                           contacts_data=get_contacts_data())


@bp.route('/about_2', methods=['GET'])
def about():
    try:
        Partner.query.filter_by(name='temp').delete()
        Employee.query.filter_by(name='temp').delete()
        db.session.commit()
    except:
        pass
    employees = Employee.query.all()
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    partners = Partner.query.all()

    return render_template('main/about.html', employees=employees,
                           filosofi=filosofi, about=about, partners=partners,
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/test_main', methods=['GET'])
def test_main():
    main_text = Text.query.filter_by(title="main_text").first().text

    temp_categories = Category.query.all()
    temp_list = []
    for category in temp_categories:
        temp_list.append(category.type)
    unique = list(set(temp_list))
    unique.sort()

    return render_template('main/new_main.html', main_text=main_text,
                           categories=get_categories(), contacts_data=get_contacts_data(), type_list=unique)


@bp.route('/reviews', methods=['GET'])
def reviews():

    comments = Comment.query.all()

    return render_template('main/comments.html', comments=comments,
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/gallery', methods=['GET'])
def gallery():
    files = listdir('app/static/images/gallery')
    return render_template('main/gallery.html',categories=get_categories(), contacts_data=get_contacts_data(), images=files)

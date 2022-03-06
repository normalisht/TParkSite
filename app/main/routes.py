from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from typing import List

from app.main import bp
from app import db
import os
import datetime
from os import listdir
from app.main.functions import get_categories, get_contacts_data
from app.models import Text, Event, Category, ServiceCategory, Service, Employee, Partner, Price
from sqlalchemy import create_engine
from flask_ckeditor import CKEditor
import shutil

engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():
    main_text = Text.query.filter_by(title="main_text").first().text
    events = Event.query.order_by(Event.date).all()

    len_slider = len(os.listdir('app/static/images/staff'))

    if len(events) == 0:
        pass
    elif len(events) < 3:
        events = events * 3

    return render_template('main/main.html', main_text=main_text, events=events[1:] + events[:1],
                           categories=get_categories(), contacts_data=get_contacts_data(),
                           len_slider=len_slider)


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
            print('1')
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





from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db
import os
from os import listdir
from app.main.functions import get_categories, get_contacts_data
from app.models import Text, Event, Category, ServiceCategory, Service, Employee, Partner, Price
from sqlalchemy import create_engine
from flask_ckeditor import CKEditor

engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():
    main_text = Text.query.filter_by(title="main_text").first().text
    events = Event.query.all()

    if len(events) == 0:
        pass
    elif len(events) < 3:
        events = events * 3
    return render_template('main/main.html', main_text=main_text, events=events[::-1],
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/admin_panel/main', methods=['GET'])
def main():
    main_text = Text.query.filter_by(title="main_text").first()
    events = Event.query.all()

    return render_template('admin_panel/main.html', title='Главная страница', main_text=main_text, events=events,
                           contacts_data=get_contacts_data())


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
        services = category.services.all()
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
                           contacts_data=get_contacts_data())


@bp.route('/service_test', methods=['GET', 'POST'])
# @login_required
def service_test():
    service_id = request.args.get('service_id')

    service = Service.query.filter_by(id=service_id).first()
    if request.method == 'POST':
        service.description = request.form.get('input_desc')
        service.price = request.form.get('input_price')
        service.name = request.form.get('title')
        db.session.commit()
    return render_template('admin_panel/service.html', title='{}'.format(service.name),
                           category=category, service=service, contacts_data=get_contacts_data())


@bp.route('/about_2', methods=['GET'])
def about():
    employees = Employee.query.all()
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    partners = Partner.query.all()

    return render_template('main/about.html', employees=employees,
                           filosofi=filosofi, about=about, partners=partners,
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/category_test', methods=['GET', 'POST'])
def category_test():
    category_id = request.args.get('category_id')
    category = Category.query.filter_by(id=category_id).first()
    services = category.services.all()
    try:
        os.chdir('app/static/images/category/{}'.format(category_id))
        temp = os.getcwd()
        files = listdir(temp)
        os.chdir('../../../../../')
    except:
        files = []
    if request.method == 'POST':
        if request.form.get('mycheckbox') == '1':
            category.status = 1
        else:
            category.status = 0
        for element in services:
            if request.form.get('service_checkbox_' + str(element.service.id)) == '1':
                element.service.status = 1
            else:
                element.service.status = 0
        category.description = request.form.get('ckeditor')
        category.name = request.form.get('title')
        db.session.commit()
    return render_template('admin_panel/category.html', title='{}'.format(category.name),
                           category=category, services=services, contacts_data=get_contacts_data(), files=files)

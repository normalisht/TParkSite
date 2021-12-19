from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db
from app.main.functions import get_categories, get_contacts_data
from app.models import Text, Event, Category, ServiceCategory, Service, Employee, Partner, Price
from sqlalchemy import create_engine

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
    print(events)

    return render_template('main/main.html', main_text=main_text, events=events,
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/category', methods=['GET'])
def category():
    try:
        category_id = request.args.get('category_id')

        category = Category.query.filter_by(id=category_id).first()
        services = category.services.all()

        return render_template('main/category.html', category=category, category_id=category_id,
                               services=services, categories=get_categories(),
                               contacts_data=get_contacts_data())
    except:
        return render_template('errors/500.html')


@bp.route('/category/service', methods=['GET'])
def service():
    service_id = request.args.get('service_id')

    service = Service.query.filter_by(id=service_id).first()

    return render_template('main/service.html', service=service, categories=get_categories(),
                           contacts_data=get_contacts_data())


@bp.route('/about', methods=['GET'])
def about():

    employees = Employee.query.all()
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    partners = Partner.query.all()

    return render_template('main/about.html', employees=employees,
                           filosofi=filosofi, about=about, partners=partners,
                           categories=get_categories(), contacts_data=get_contacts_data())

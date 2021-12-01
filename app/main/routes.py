from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db
from app.main.functions import get_categories
from app.models import Text, Event, Category, ServiceCategory, Service, Employee, Partner
from sqlalchemy import create_engine

engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():
    main_text = Text.query.filter_by(title="main_text").first().text
    events = Event.query.all()
    geolocation = Text.query.filter_by(title='geolocation').first()
    address = Text.query.filter_by(title='address').first()
    phone_numbers = Text.query.filter_by(title='phone_numbers').first()
    vk = Text.query.filter_by(title='vk').first()
    insta = Text.query.filter_by(title='insta').first()

    return render_template('main/main.html', main_text=main_text, events=events,
                           categories=get_categories(), geolocation=geolocation,
                           address=address, phone_numbers=phone_numbers,
                           insta=insta, vk=vk)


@bp.route('/category', methods=['GET'])
def test():
    try:
        category_id = request.args.get('category_id')

        category = Category.query.filter_by(id=category_id).first()
        services = category.services.all()

        return render_template('main/category.html', category=category, category_id=category_id,
                               services=services, categories=get_categories())
    except:
        return render_template('errors/500.html')


@bp.route('/category/service', methods=['GET'])
def service():
    service_id = request.args.get('service_id')

    service = Service.query.filter_by(id=service_id).first()

    return render_template('main/service.html', service=service, categories=get_categories())


@bp.route('/about', methods=['GET'])
def about():

    employees = Employee.query.all()
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    partners = Partner.query.all()

    return render_template('main/about.html', employees=employees,
                           filosofi=filosofi, about=about, partners=partners,
                           categories=get_categories())

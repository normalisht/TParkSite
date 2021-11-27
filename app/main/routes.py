from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db
from app.models import Text, Event, Category, ServiceCategory, Service
from sqlalchemy import create_engine

engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():
    main_text = Text.query.filter_by(title="main_text").first().text
    events = Event.query.all()

    return render_template('main/main.html', main_text=main_text, events=events)


@bp.route('/category/<category_id>', methods=['GET'])
def test(category_id):
    category = Category.query.filter_by(id=category_id).first()
    try:
        a = engine.execute("SELECT service_id FROM service_category WHERE category_id = ?", category.id)
        a = a.fetchall()
        f = []
        for row in a:
            f.append(row[0])
        service = Service.query.filter(Service.id.in_(f)).all()

        return render_template('category/category.html', category=category, category_id=category_id, services=service)


    except:
        return render_template('errors/500.html')


@bp.route('/category/service', methods=['GET'])
def service():
    service_id = request.args.get('service_id')
    service = Service.query.filter_by(id=service_id).first()

    return render_template('main/service.html', service=service)

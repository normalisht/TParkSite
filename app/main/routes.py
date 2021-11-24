from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db
from app.models import Text, Category, ServiceCategory, Service
from sqlalchemy import create_engine

engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():

    main_text = Text.query.filter_by(title="main_text").first().text

    return render_template('main/main.html', main_text=main_text)


@bp.route('/category/<category_id>', methods=['GET'])
def test(category_id):
    try:
        category = Category.query.filter_by(id=category_id).first()
        services = category.services.all()

        return render_template('category/category.html', category=category, category_id=category_id, services=services)
    except:
        return render_template('errors/500.html')


from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db
from app.models import Text


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():

    main_text = Text.query.filter_by(title="main_text").first().text

    return render_template('main/main.html', main_text=main_text)




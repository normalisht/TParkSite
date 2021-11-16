from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.main import bp
from app import db


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():

    return render_template('main/main.html')

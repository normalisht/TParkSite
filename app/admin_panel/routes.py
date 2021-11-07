from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.admin_panel import bp
from app import db
from flask_login import login_user, logout_user, current_user, login_required
from app.models import Admin, Category, Service, Employee, Text, Comment
from werkzeug.urls import url_parse


# авторизация админа
@bp.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        admin = Admin.query.filter_by(email=request.form.get('email').lower()).first()
        if admin is None or not admin.check_password(request.form.get('password')):
            flash('Неверный пароль или email', 'warning')
            return redirect(url_for('admin_panel.login'))

        login_user(admin, remember=request.form.get('remember'))
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('admin_panel/login.html', title='Авторизация')


# выход
@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/menu', methods=['GET'])
@login_required
def menu():

    categories = Category.query.all()

    return render_template('admin_panel/menu.html', title='Меню', categories=categories)


@bp.route('/texts', methods=['GET'])
@login_required
def texts():

    texts = Text.query.all()

    return render_template('admin_panel/texts.html', title='Описания/Тексты',
                           texts=texts)


@bp.route('/employees', methods=['GET'])
@login_required
def employees():

    employees = Employee.query.all()

    return render_template('admin_panel/employees.html', title='Содрудники',
                           employees=employees)


@bp.route('/category', methods=['GET'])
@login_required
def category():

    id = request.args.get('id')

    category = Category.query.filter_by(id=id).first()
    services = category.services.all()

    return render_template('admin_panel/category.html', title='{}'.format(category.name),
                           category=category, services=services)


@bp.route('/service', methods=['GET'])
@login_required
def service():

    id = request.args.get('id')

    service = Service.query.filter_by(id=id).first()

    return render_template('admin_panel/service.html', title='{}'.format(category.name),
                           category=category, service=service)

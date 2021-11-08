from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from app.admin_panel import bp
from app import db
from flask_login import login_user, logout_user, current_user, login_required
from app.models import Admin, Category, Service, Employee, Text, Comment, ServiceCategory
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


@bp.route('/service', methods=['GET'])
@login_required
def comments():
    comments = Comment.query.all()

    return render_template('admin_panel/comments.html', title='Отзывы', comments=comments)


# далее json запросы

@bp.route('/update_service', methods=['POST'])
def update_service():
    service = Service.query.filter_by(id=request.form['id']).first()

    if getattr(service, 'name') != request.form['name']:
        setattr(service, 'name', request.form['name'])

    if getattr(service, 'price') != request.form['price']:
        setattr(service, 'price', request.form['price'])

    if getattr(service, 'short_description') != request.form['short_description']:
        setattr(service, 'short_description', request.form['short_description'])

    if getattr(service, 'description') != request.form['description']:
        setattr(service, 'description', request.form['description'])

    if getattr(service, 'number') != request.form['number']:
        setattr(service, 'number', request.form['number'])

    if getattr(service, 'status') != request.form['status']:
        setattr(service, 'status', request.form['status'])

    return jsonify({'result': 'success'})


@bp.route('/add_category_for_service', methods=['POST'])
def add_category_for_service():
    service_category = ServiceCategory(
        service_id=request.form['service_id'],
        category_id=request.form['category_id'])

    db.session.add(service_category)
    db.session.commit()

    return jsonify({'result': 'success'})


@bp.route('/remove_category_for_service', methods=['POST'])
def remove_category_for_service():
    service_category = ServiceCategory.query.filter_by(
        service_id=request.form['service_id'],
        category_id=request.form['category_id'])

    db.session.delete(service_category)
    db.session.commit()

    return jsonify({'result': 'success'})

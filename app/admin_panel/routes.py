import datetime
import os
from os import listdir

from flask import render_template, flash, redirect, url_for, request, jsonify, current_app

from app.admin_panel import bp
from app import db
from flask_login import login_user, logout_user, current_user, login_required

from app.main.functions import get_categories
from app.models import Admin, Category, Service, Employee, Text, Comment, ServiceCategory, Event, Partner
import json


# авторизация админа
@bp.route('/', methods=['GET', 'POST'])
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_panel.main'))

    if request.method == 'POST':
        admin = Admin.query.filter_by(email=request.form.get('email').lower()).first()
        if admin is None or not admin.check_password(request.form.get('password')):
            flash('Неверный пароль или email', 'warning')
            return redirect(url_for('admin_panel.login'))

        return redirect(url_for('admin_panel.main'))

    return render_template('admin_panel/login.html', title='Авторизация')


# выход
@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/main', methods=['GET'])
# @login_required
def main():
    main_text = Text.query.filter_by(title="main_text").first()

    return render_template('admin_panel/main.html', title='Главная страница', main_text=main_text,
                           categories=get_categories())


# Все ивенты
@bp.route('/events', methods=['GET'])
# @login_required
def events():
    events = Event.query.all()

    return render_template('admin_panel/event/events.html', title='Мероприятия',
                           events=events)


# создание ивента
@bp.route('/event_create', methods=['GET', 'POST'])
# @login_required
def event_create():
    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date').split('-')
        description = request.form.get('description')
        link = request.form.get('link')

        date = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), 22)

        event = Event(title=title, date=date, description=description, link=link)
        db.session.add(event)
        db.session.commit()

        photo = request.files['photo']
        photo.save(os.path.join(os.getcwd(), '{}.png'.format(
            Event.query.filter_by(title=title, link=link).first().id
        )))

        return redirect(url_for('admin_panel.events'))

    return render_template('admin_panel/event/event_create.html', title='Создание мероприятия')


# радактирование ивента
@bp.route('/event_edit/<id>', methods=['GET', 'POST'])
# @login_required
def event_edit(id):
    event = Event.query.filter_by(id=id).first()

    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date').split('-')
        description = request.form.get('description')
        link = request.form.get('link')

        date = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), 22)

        setattr(event, 'title', title)
        setattr(event, 'description', description)
        setattr(event, 'date', date)
        setattr(event, 'link', link)

        try:
            photo = request.files['photo']
            photo.save(os.path.join(os.getcwd(), '{}.png'.format(
                Event.query.filter_by(title=title, link=link).first().id
            )))
        except:
            pass

        db.session.commit()

        return redirect(url_for('admin_panel.events'))

    return render_template('admin_panel/event/event_edit.html', event=event,
                           title='Редактирование мероприятия')


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
                           category=category, services=services, files=files)


@bp.route('/category_create', methods=['GET', 'POST'])
# @login_required
def category_create():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')

        category = Category(name=title, description=description, status=1)
        db.session.add(category)
        db.session.commit()

        photo = request.files['photo']
        category_id = category.id
        os.makedirs('app/static/images/category/{}'.format(category_id))
        os.chdir('app/static/images/category/{}'.format(category_id))
        photo.save(os.path.join(os.getcwd(), '{}.png'.format(
            Category.query.filter_by(name=title).first().id
        )))
        os.chdir('../../../../../')

    return render_template('admin_panel/category_create.html', title='Создание категории')


@bp.route('/service_test', methods=['GET', 'POST'])
# @login_required
def service_test():
    service_id = request.args.get('service_id')

    service = Service.query.filter_by(id=service_id).first()
    if request.method == 'POST':
        if request.form.get('checkbox') == '1':
            service.next = 1
        else:
            service.next = 0

        service.short_description = request.form.get('input_short_desc')
        service.description = request.form.get('input_desc')
        service.price = request.form.get('input_price')
        service.name = request.form.get('title')
        # if request.files['photo']:
        #     photo = request.files['photo']
        #     photo.save(os.path.join(os.getcwd(), 'service_id.png'.format(service.number)))
        # service.categories = request.form.get('categories')
        db.session.commit()
    return render_template('admin_panel/service.html', title='{}'.format(service.name),
                           categories=get_categories(), service=service)


@bp.route('/service_create', methods=['GET', 'POST'])
# @login_required
def service_create():
    if request.method == 'POST':
        title = request.form.get('title')
        short_description = request.form.get('short_description')
        description = request.form.get('description')
        price = request.form.get('price')
        next = request.form.get('next')

        service = Service(name=title, description=description, short_description=short_description, price=price,
                          next=next, status=1)
        db.session.add(service)
        db.session.commit()

        photo = request.files['photo']
        photo.save(os.path.join(os.getcwd(), '{}.png'.format(
            Service.query.filter_by(name=title).first().id
        )))

    return render_template('admin_panel/service_create.html', title='Создание услуги')


@bp.route('/about_2', methods=['GET'])
def about():
    employees = Employee.query.all()
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    partners = Partner.query.all()

    return render_template('admin_panel/about.html', employees=employees,
                           filosofi=filosofi, about=about, partners=partners)


'''json запросы'''

'''услуги'''


# обновляет данные об услуге
@bp.route('/update_service', methods=['POST'])
@login_required
def update_service():
    service = Service.query.filter_by(id=request.form['id']).first()
    #
    # if getattr(service, 'name') != request.form['name']:
    #     setattr(service, 'name', request.form['name'])
    #
    # if getattr(service, 'price') != int(request.form['price']):
    #     setattr(service, 'price', int(request.form['price']))
    #
    # if getattr(service, 'short_description') != request.form['short_description']:
    #     setattr(service, 'short_description', request.form['short_description'])
    #
    # if getattr(service, 'description') != request.form['description']:
    #     setattr(service, 'description', request.form['description'])
    #
    # if getattr(service, 'number') != int(request.form['number']):
    #     setattr(service, 'number', int(request.form['number']))
    #
    # if getattr(service, 'status') != bool(int(request.form['status'])):
    #     setattr(service, 'status', bool(int(request.form['status'])))

    return jsonify({'result': 'success'})


# добавляет услугу к категории
@bp.route('/add_category_for_service', methods=['POST'])
@login_required
def add_category_for_service():
    service_category = ServiceCategory(
        service_id=request.form['service_id'],
        category_id=request.form['category_id'])

    db.session.add(service_category)
    db.session.commit()

    return jsonify({'result': 'success'})


# удаляет услугу из категории
@bp.route('/remove_category_for_service', methods=['POST'])
@login_required
def remove_category_for_service():
    service_category = ServiceCategory.query.filter_by(
        service_id=request.form['service_id'],
        category_id=request.form['category_id'])

    db.session.delete(service_category)
    db.session.commit()

    return jsonify({'result': 'success'})


# добавляет услугу
@bp.route('/add_new_service', methods=['POST'])
@login_required
def add_new_service():
    service = Service(name=request.form['name'], price=request.form['price'],
                      short_description=request.form['short_description'],
                      description=request.form['description'],
                      status=True)
    db.session.add(service)
    db.session.commit()

    for category_id in list(json.loads(request.form['categories'])):
        service_category = ServiceCategory(
            service=service.id, category_id=category_id)
        db.session.add(service_category)
        db.session.commit()

    return jsonify({'result': 'success'})


# удаляет услугу
@bp.route('/remove_service', methods=['POST'])
@login_required
def remove_service():
    service = Service.query.filter_by(id=request.form['id'])

    for category in service.categories.all():
        db.session.delete(category)
        db.session.commit()

    db.session.delete(service)
    db.session.commit()

    return jsonify({'result': 'success'})


'''категории'''


# добавляет новую категорию
@bp.route('/add_new_category', methods=['POST'])
@login_required
def add_new_category():
    category = Category(name=request.form['name'], status=True,
                        description=request.form['description'])

    db.session.add(category)
    db.session.commit()

    return jsonify({'result': 'success'})


# удаляет категорию
@bp.route('/remove_category', methods=['POST'])
@login_required
def remove_category():
    category = Category.query.filter_by(id=request.form['id'])

    for service in category.services.all():
        db.session.delete(service)
        db.session.commit()

    db.session.delete(category)
    db.session.commit()

    return jsonify({'result': 'success'})


# обновляет данные о категории
@bp.route('/update_category', methods=['POST'])
@login_required
def update_category():
    category = Category.query.filter_by(id=request.form['id'])

    if getattr(category, 'name') != request.form['name']:
        setattr(category, 'name', request.form['name'])

    if getattr(category, 'description') != request.form['description']:
        setattr(category, 'description', request.form['description'])

    if getattr(category, 'number') != int(request.form['number']):
        setattr(category, 'number', int(request.form['number']))

    if getattr(category, 'status') != bool(int(request.form['status'])):
        setattr(category, 'status', bool(int(request.form['status'])))

    return jsonify({'result': 'success'})


'''сотрудники'''


# добавляет сотрудника
@bp.route('/add_employee', methods=['POST'])
@login_required
def add_employee():
    employee = Employee(name=request.form['name'], position=request.form['position'],
                        phone=request.form['photo'])

    db.session.add(employee)
    db.session.commit()

    return jsonify({'result': 'success'})


# удаляет сотрудника
@bp.route('/remove_employee', methods=['POST'])
@login_required
def remove_employee():
    employee = Employee.query.filter_by(id=request.form['id']).first()

    db.session.delete(employee)
    db.session.commit()

    return jsonify({'result': 'success'})


# обновляет данные о сотруднике
@bp.route('/update_employee', methods=['POST'])
@login_required
def update_employee():
    employee = Employee.query.filter_by(id=request.form['id']).first()

    if getattr(employee, 'name') != request.form['name']:
        setattr(employee, 'name', request.form['name'])

    if getattr(employee, 'position') != request.form['position']:
        setattr(employee, 'position', request.form['position'])

    if getattr(employee, 'photo') != request.form['photo']:
        setattr(employee, 'photo', request.form['photo'])

    return jsonify({'result': 'success'})


'''Тексты'''


# обновляет данные тексте
@bp.route('/update_text', methods=['POST'])
# @login_required
def update_text():
    text = Text.query.filter_by(id=request.form['id']).first()

    # if getattr(text, 'title') != request.form['title']:
    #     setattr(text, 'title', request.form['title'])

    if getattr(text, 'text') != request.form['text']:
        setattr(text, 'text', request.form['text'])

    # if getattr(text, 'photo') != request.form['photo']:
    #     setattr(text, 'photo', request.form['photo'])

    return jsonify({'result': 'success'})


'''отзывы'''


# добавляет отзыв
@bp.route('/add_comment', methods=['POST'])
@login_required
def add_comment():
    comment = Comment(name=request.form['name'], text=request.form['text'])

    db.session.add(comment)
    db.session.commit()

    return jsonify({'result': 'success'})


# удаляет отзыв
@bp.route('/remove_comment', methods=['POST'])
@login_required
def remove_comment():
    comment = Comment.query.filter_by(id=request.form['id']).first()

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'result': 'success'})


# обновляет отзыв
@bp.route('/update_comment', methods=['POST'])
@login_required
def update_comment():
    comment = Comment.query.filter_by(id=request.form['id']).first()

    if getattr(comment, 'name') != request.form['name']:
        setattr(comment, 'name', request.form['name'])

    if getattr(comment, 'text') != request.form['text']:
        setattr(comment, 'text', request.form['text'])

    return jsonify({'result': 'success'})

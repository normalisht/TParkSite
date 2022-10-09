from flask import render_template, redirect, url_for, request
from app.main import bp
from app import db
import os
import datetime
from random import shuffle
from os import listdir
from app.models import Text, Comment, Event, Category, ServiceCategory, Service, Employee, Partner, Type
from app.main.functions import get_categories, get_contacts_data
from sqlalchemy import create_engine


engine = create_engine("sqlite:///T_Park.db")


@bp.route('/', methods=['GET'])
@bp.route('/TPark', methods=['GET'])
def index():
    main_text = Text.query.filter_by(title="main_text").first().text
    types = Type.query.order_by(Type.number).all()

    return render_template('main/new_main.html', main_text=main_text,
                           contacts_data=get_contacts_data(), types=types)


@bp.route('/category', methods=['GET'])
def category():
    try:
        category_id = request.args.get('category_id')
        try:
            files = listdir('app/static/images/category/{}'.format(category_id))
            path = os.path.join('app/static/images/category/{}'.format(category_id), files[0])
            open(path)
            photo = True
        except:
            photo = False
            files = []

        category = Category.query.filter_by(id=category_id).first()
        services = category.services.order_by(ServiceCategory.number).all()

        if category.status == 1:
            return render_template('main/category.html', category=category, category_id=category_id,
                                   services=services, categories=get_categories(), files=files,
                                   contacts_data=get_contacts_data(), photo=photo)
        else:
            return redirect(url_for('main.index'))
    except:
        return render_template('errors/500.html')


@bp.route('/category/service', methods=['GET'])
def service():
    service_id = request.args.get('service_id')

    service = Service.query.filter_by(id=service_id).first()

    photo = False
    if os.path.exists('app/static/images/service/{}.png'.format(service_id)):
        photo = True

    print(photo)

    return render_template('main/service.html', service=service, categories=get_categories(),
                           photo=photo, contacts_data=get_contacts_data())


@bp.route('/about_2', methods=['GET'])
def about():
    try:
        Partner.query.filter_by(name='temp').delete()
        Employee.query.filter_by(name='temp').delete()
        db.session.commit()
    except:
        pass
    employees = Employee.query.all()
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    partners = Partner.query.all()

    return render_template('main/about.html', employees=employees,
                           filosofi=filosofi, about=about, partners=partners,
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/events', methods=['GET'])
def events():
    main_text = Text.query.filter_by(title="main_text").first().text
    events = Event.query.order_by(Event.date).all()
    events_2 = []
    slider_events = True
    len_slider = len(os.listdir('app/static/images/staff'))
    # len_slider = len(os.listdir('/home/Losharik17/TParkSite/app/static/images/staff'))

    for event in events:
        date = datetime.date(int(event.date.strftime('%Y')), int(event.date.strftime('%m')),
                             int(event.date.strftime('%d')))
        dt = datetime.datetime.combine(date, datetime.time(22, 0))

        if dt > datetime.datetime.now():
            events_2.append(event)

    if len(events_2) == 0:
        slider_events = False
    elif len(events_2) < 3:
        events_2 = events_2 * 3

    print(events_2)

    return render_template('main/main.html', main_text=main_text, events=events_2[1:] + events_2[:1],
                           categories=get_categories(), contacts_data=get_contacts_data(),
                           len_slider=len_slider, slider_events=slider_events)


@bp.route('/reviews', methods=['GET'])
def reviews():
    comments = Comment.query.all()

    comments.sort(key=lambda x: len(x.text))
    photos = []
    names = []
    comments1 = []
    comments2 = []

    for index, comment in enumerate(comments):
        if index == 0:
            print(1)
            comments1.append(comment)
            count = 2
            continue
        if count < 2:
            count += 1
            print(1)
            comments1.append(comment)
        elif count < 4:
            print(2)
            count += 1
            comments2.append(comment)
        if count == 4:
            count = 0
    shuffle(comments1)
    shuffle(comments2)
    comments = comments1 + comments2

    for comment in comments:
        photos.append(os.path.exists(f'app/static/images/comments/{comment.id}.png'))
        names.append(comment.name)

    return render_template('main/comments.html', comments=comments, names=names, photos=photos,
                           categories=get_categories(), contacts_data=get_contacts_data())


@bp.route('/gallery', methods=['GET'])
def gallery():
    files = listdir('app/static/images/gallery')
    return render_template('main/gallery.html', categories=get_categories(), contacts_data=get_contacts_data(),
                           images=files)
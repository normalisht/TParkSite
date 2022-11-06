import datetime
import os
from os import listdir
from flask import render_template, flash, redirect, url_for, request
from werkzeug.urls import url_parse
from app.admin_panel import bp
from app import db
from flask_login import login_user, logout_user, current_user, login_required
from app.main.functions import get_categories, get_contacts_data
from app.models import CategoryType, Admin, Category, Service, Employee, Text, Comment, ServiceCategory, Event, Partner, \
    Type
import shutil
from PIL import Image
from math import floor


def get_size_format(b, factor=1024, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"


def compress_img(image_name, new_size_ratio=1, quality=50, width=None, height=None, to_jpg=True):
    # load the image to memory
    img = Image.open(image_name)
    # print the original image shape
    # print("[*] Image shape:", img.size)
    # get the original image size in bytes
    image_size = os.path.getsize(image_name)
    # print the size before compression/resizing
    print("[*] Size before compression:", get_size_format(image_size))
    if new_size_ratio < 1.0:
        # if resizing ratio is below 1.0, then multiply width & height with this ratio to reduce image size
        img = img.resize((int(img.size[0] * new_size_ratio), int(img.size[1] * new_size_ratio)), Image.ANTIALIAS)
        # print new image shape
        # print("[+] New Image shape:", img.size)
    elif width and height:
        # if width and height are set, resize with them instead
        img.thumbnail((width, height), Image.ANTIALIAS)
        # print new image shape
        # print("[+] New Image shape:", img.size)
    # split the filename and extension
    filename, ext = os.path.splitext(image_name)
    # make new filename appending _compressed to the original file name
    if to_jpg:
        # change the extension to JPEG
        new_filename = f"{filename}.jpg"
    else:
        # retain the same extension of the original image
        new_filename = f"{filename}{ext}"
    try:
        # save the image with the corresponding quality and optimize set to True
        img.save(new_filename, quality=quality, optimize=True)
    except OSError:
        # convert the image to RGB mode first
        img = img.convert("RGB")
        # save the image with the corresponding quality and optimize set to True
        img.save(new_filename, quality=quality, optimize=True)
    # print("[+] New file saved:", new_filename)
    # get the new image size in bytes
    new_image_size = os.path.getsize(new_filename)
    # print the new size in a good format
    # print("[+] Size after compression:", get_size_format(new_image_size))
    # calculate the saving bytes
    saving_diff = new_image_size - image_size
    # print the saving percentage
    print(f"[+] Image size change: {saving_diff/image_size*100:.2f}% of the original image size.")


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

        login_user(admin, remember=True)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('admin_panel.main')
        return redirect(next_page)

    return render_template('admin_panel/login.html', title='Авторизация')


# выход
@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/main', methods=['GET', 'POST'])
@login_required
def main():
    categories = Category.query.order_by(Category.number).all()

    return render_template('admin_panel/categories.html', title='Категории',
                           categories=categories)


@bp.route('/events_content', methods=['GET', 'POST'])
@login_required
def events_content():
    main_text = Text.query.filter_by(title="main_text").first()

    try:
        files = listdir('app/static/images/events/')
        path = os.path.join('app/static/images/events/', files[0])
        open(path)
    except:
        files = []

    if request.method == 'POST':

        setattr(main_text, 'text', request.form.get('title'))

        db.session.commit()

        for photo in files:
            if request.form.get('delete_' + str(photo)):
                try:
                    os.remove('app/static/images/events/' + str(photo))
                    return redirect(url_for('admin_panel.main'))
                except:
                    pass
            if request.files.get('change_' + str(photo)):
                image = request.files.get('change_' + str(photo))
                path = os.path.join('app/static/images/events', '{}.jpg'.format(os.path.splitext(photo)[0]))
                image.save(path)
                compress_img(path, width=1920, height=1080, quality=95)
                return redirect(url_for('admin_panel.main'))
        if files[0] != '0.jpg':
            name = 0
        elif files[1] != '1.jpg':
            name = 1
        else:
            name = 2
        if request.files.get('add_photo'):
            images = request.files.get('add_photo')
            path = os.path.join('app/static/images/events/', '{}.jpg'.format(name))
            images.save(path)
            compress_img(path, width=1920, height=1080, quality=95)

            return redirect(url_for('admin_panel.events_content'))

    return render_template('admin_panel/main.html', title='Страница событий', main_text=main_text,
                           categories=get_categories(), files=files)


# Все ивенты
@bp.route('/events', methods=['GET'])
@login_required
def events():
    events = []
    events_2 = []

    for event in Event.query.order_by(Event.date).all():
        date = datetime.date(int(event.date.strftime('%Y')), int(event.date.strftime('%m')),
                             int(event.date.strftime('%d')))
        dt = datetime.datetime.combine(date, datetime.time(22, 0))

        if dt > datetime.datetime.now():
            events.append(event)
        else:
            events_2.append(event)

    return render_template('admin_panel/event/events.html', title='Мероприятия',
                           events=events, events_2=events_2)


# создание ивента
@bp.route('/event_create', methods=['GET', 'POST'])
@login_required
def event_create():
    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date').split('-')
        description = request.form.get('description')
        link = request.form.get('link')
        color = request.form.get('color')

        date = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), 22)

        event = Event(title=title, date=date, description=description, link=link, text_color=color)
        db.session.add(event)
        db.session.commit()

        photo = request.files['photo']
        path = os.path.join('app/static/images/events/', '{}.jpg'.format(
            Event.query.filter_by(title=title, link=link).first().id))
        photo.save(path)
        compress_img(path, width=1920, height=1080, quality=95)

        return redirect(url_for('admin_panel.events'))

    return render_template('admin_panel/event/event_create.html', title='Создание мероприятия')


# радактирование ивента
@bp.route('/event_edit', methods=['GET', 'POST'])
@login_required
def event_edit():
    id = request.args.get('event_id')

    event = Event.query.filter_by(id=id).first()

    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date').split('-')
        description = request.form.get('description')
        link = request.form.get('link')
        text_color = request.form.get('color')

        date = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), 22)

        setattr(event, 'title', title)
        setattr(event, 'description', description)
        setattr(event, 'date', date)
        setattr(event, 'link', link)
        setattr(event, 'text_color', text_color)

        try:
            if request.files.get('change'):
                image = request.files.get('change')
                path = os.path.join('app/static/images/events', '{}.jpg'.format(event.id))
                image.save(path)
                compress_img(path, width=1920, height=1080, quality=95)
        except:
            pass

        db.session.commit()

        if request.form.get('delete'):
            db.session.delete(event)
            db.session.commit()

            return redirect(url_for('admin_panel.events'))

    return render_template('admin_panel/event/event_edit.html', event=event,
                           title='Редактирование мероприятия')


@bp.route('/category', methods=['GET'])
@login_required
def category():
    categories = Category.query.order_by(Category.number).all()

    return render_template('admin_panel/categories.html', title='Категории',
                           categories=categories)


@bp.route('/category_change', methods=['GET', 'POST'])
@login_required
def category_change():
    base_number = 1
    category_id = request.args.get('category_id')
    category = Category.query.filter_by(id=category_id).first()
    services = category.services.order_by(ServiceCategory.number).all()
    numbers = []  # хранит порядковые номера услуг

    try:
        files = listdir('app/static/images/category/{}'.format(category_id))
    except:
        files = []

    for element in services:
        numbers.append(element.number)

    if request.method == 'POST':
        if request.form.get('mycheckbox') == '1':
            category.status = 1
        else:
            category.status = 0

        for element in services:
            if request.form.get('service_checkbox_' + str(element.service.id)) != '1':
                el = ServiceCategory.query.filter_by(service_id=element.service.id,
                                                     category_id=category_id).first()
                db.session.delete(el)
                db.session.commit()

            number = request.form.get('service_number_' + str(element.service.id))
            if number:
                setattr(element, 'number', number)

        if request.form.get('delete_category'):
            try:
                shutil.rmtree('app/static/images/category/{}'.format(category_id), ignore_errors=True)
            except:
                pass

            CategoryType.query.filter_by(category_id=category.id).delete()
            Category.query.filter_by(id=category_id).delete()
            db.session.commit()
            return redirect(url_for('admin_panel.category'))

        for photo in files:
            if request.form.get('delete_' + str(photo)):
                try:
                    os.remove('app/static/images/category/{}/'.format(category_id) + str(photo))
                except:
                    pass

            if request.files['add_' + str(photo)]:
                images = request.files.getlist('add_' + str(photo))
                count = len(files)

                for img in images:
                    path = os.path.join('app/static/images/category/{}'.format(category_id), '{}.jpg'.format(coun))
                    img.save(path)
                    compress_img(path, width=1920, height=1080, quality=95)
                    count += 1

        if request.files.get('add_photo'):
            images = request.files.getlist('add_photo')
            count = len(files) + 1
            for img in images:
                path = os.path.join('app/static/images/category/{}'.format(category_id), '{}.jpg'.format(count + 2))
                img.save(path)
                compress_img(path, width=1920, height=1080, quality=95)
                count += 1

        if request.files.get('add_preview'):
            img = request.files.get('add_preview')
            path = os.path.join('app/static/images/category/preview', '{}.jpg'.format(category_id))
            img.save(path)
            compress_img(path, width=1080, height=720, quality=80)

        category.number = request.form.get('weight')
        category.description = request.form.get('ckeditor')
        category.name = request.form.get('title').strip().capitalize()
        db.session.commit()
        return redirect(url_for('admin_panel.category_change', category_id=category_id))

    services = category.services.order_by(ServiceCategory.number).all()

    return render_template('admin_panel/category.html', title='{}'.format(category.name),
                           category=category, services=services, numbers=numbers, files=files)


@bp.route('/category_create', methods=['GET', 'POST'])
@login_required
def category_create():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')

        category = Category(name=title, description=description, status=0)
        db.session.add(category)
        db.session.commit()
        category_id = category.id
        os.makedirs('app/static/images/category/{}'.format(category_id))
        try:
            photo = request.files.getlist('photo')
            count = 1
            if photo[0]:
                for file in photo:
                    path = os.path.join('app/static/images/category/{}'.format(category_id), '{}.jpg'.format(count))
                    file.save(path)
                    compress_img(path, width=1920, height=1080, quality=95)
                    count += 1
        except:
            pass

    return render_template('admin_panel/category_create.html', title='Создание категории')


@bp.route('/service_test', methods=['GET', 'POST'])
@login_required
def service_test():
    service_id = request.args.get('service_id')
    service = Service.query.filter_by(id=service_id).first()
    categories_all = Category.query.order_by(Category.number).all()

    try:
        files = listdir('app/static/images/service/{}'.format(service_id))
    except:
        files = []

    categories_cheked = []
    for category in categories_all:
        if ServiceCategory.query.filter_by(service_id=service_id, category_id=category.id).first():
            categories_cheked.insert(category.id, category.id)
        else:
            categories_cheked.insert(category.id, 0)

    if request.method == 'POST':
        if request.form.get('checkbox') == '1':
            service.next = 1
        else:
            service.next = 0

        for category in categories_all:
            a = ServiceCategory(service_id=service_id, category_id=category.id)

            if request.form.get(str(category.id)) == str(category.id):
                if not ServiceCategory.query.filter_by(service_id=service_id, category_id=category.id).first():
                    db.session.add(a)
                    db.session.commit()
            else:
                x = ServiceCategory.query.filter_by(service_id=service_id, category_id=category.id).first()
                if x:
                    db.session.delete(x)
                    db.session.commit()

        db.session.commit()

        # checking categories(if it in ServiceCategories -> 1)

        if request.form.get('delete'):
            try:
                os.remove('app/static/images/service/' + str(service.id) + ".jpg")
            except:
                pass

        for photo in files:
            if request.form.get('delete_' + str(photo)):
                print(str(photo))
                try:
                    os.remove('app/static/images/service/{}/'.format(service_id) + str(photo))
                except:
                    pass

            if request.files['add_' + str(photo)]:
                images = request.files.getlist('add_' + str(photo))
                count = len(files)

                for img in images:
                    path = os.path.join('app/static/images/service/{}'.format(service_id), '{}.jpg'.format(count))
                    img.save(path)
                    compress_img(path, width=1920, height=1080, quality=95)
                    count += 1

        if request.files.get('add_photo'):
            images = request.files.getlist('add_photo')
            count = len(files) + 1
            for img in images:
                path = os.path.join('app/static/images/service/{}'.format(service_id), '{}.jpg'.format(count + 2))
                img.save(path)
                compress_img(path, width=1920, height=1080, quality=95)
                count += 1

        service.short_description = request.form.get('input_short_desc')
        service.description = request.form.get('input_desc')
        service.name = request.form.get('title')

        service.price = request.form.get('input_price')
        service.time = request.form.get('input_price_time')
        db.session.commit()

        if request.form.get('delete_service'):
            try:
                shutil.rmtree('app/static/images/service/{}'.format(service_id), ignore_errors=True)
            except:
                pass

            ServiceCategory.query.filter_by(service_id=service_id).delete()
            Service.query.filter_by(id=service_id).delete()
            db.session.commit()

            return redirect(url_for('admin_panel.all_services'))

        if len(service.categories.all()) > 0:
            return redirect(
                url_for('admin_panel.category_change') + '?category_id={}'.format(service.categories.all()[0].category_id))

    categories_cheked = []
    for category in categories_all:
        if ServiceCategory.query.filter_by(service_id=service_id, category_id=category.id).first():
            categories_cheked.insert(category.id, category.id)
        else:
            categories_cheked.insert(category.id, 0)

    return render_template('admin_panel/service.html', title='{}'.format(service.name), files=files,
                           categories=get_categories(), service=service, categories_checked=categories_cheked)


@bp.route('/service_create', methods=['GET', 'POST'])
@login_required
def service_create():
    categories_all = Category.query.all()
    service_all = Service.query.all()
    service_number = service_all[-1]
    service_id = service_number.id + 1
    b = [0]
    if request.method == 'POST':
        title = request.form.get('title')
        short_description = request.form.get('short_description')
        description = request.form.get('description')
        price = request.form.get('price')
        time = request.form.get('price_time')
        next = 0 if request.form.get('next') == None else 1

        for category in categories_all:
            a = ServiceCategory(service_id=service_id, category_id=category.id)
            print(a.service_id)
            if request.form.get(str(category.id)) == str(category.id):
                if not ServiceCategory.query.filter_by(service_id=service_id, category_id=category.id).first():
                    db.session.add(a)
                    db.session.commit()
            else:
                x = ServiceCategory.query.filter_by(service_id=service_id, category_id=category.id).first()
                if x:
                    db.session.remove(x)
                    db.session.commit()

        db.session.commit()
        service = Service(name=title, description=description, short_description=short_description,
                          price=price, time=time, next=next, status=1)

        db.session.add(service)
        db.session.commit()

        # photo = request.files['photo']
        # if photo:
        #     photo.save(os.path.join(os.getcwd(), '{}.jpg'.format(
        #         Service.query.filter_by(name=title).first().id
        #     )))

        return redirect(url_for('admin_panel.service_test') + '?service_id={}'.format(service_id))

    return render_template('admin_panel/service_create.html', title='Создание услуги',
                           categories=categories_all, categories_checked=b)


@bp.route('/all_services', methods=['GET'])
@login_required
def all_services():
    services = Service.query.order_by(Service.name).all()

    return render_template('admin_panel/all_services.html', services=services)


@bp.route('/about_2', methods=['GET', 'POST'])
@login_required
def about():
    about = Text.query.filter_by(title='about').first()
    filosofi = Text.query.filter_by(title='filosofi').first()
    structure = Text.query.filter_by(title='structure').first()

    if not Partner.query.filter_by(name='temp').first():
        db.session.add(Partner(name='temp'))
        db.session.commit()

    partners = Partner.query.all()

    if request.method == 'POST':
        for partner in partners:
            if request.form.get('partner_' + str(partner.id) + '_delete'):
                try:
                    os.remove('app/static/images/partner/' + str(partner.id) + ".jpg")
                except:
                    pass
                Partner.query.filter_by(id=partner.id).delete()
                db.session.commit()
                continue

            if request.form.get('partner_' + str(partner.id) + '_save') and partner.name != 'temp':
                if request.files.get('partner_' + str(partner.id) + '_photo'):
                    image = request.files.get('partner_' + str(partner.id) + '_photo')
                    path = os.path.join('app/static/images/partner', '{}.jpg'.format(partner.id))
                    image.save(path)
                    compress_img(path, width=1920, height=1080)
                partner.link = request.form.get('partner_' + str(partner.id) + '_link')

        if request.form.get('about_text'):
            about.text = request.form.get('about_text')
        if request.form.get('filosofi_text'):
            filosofi.text = request.form.get('filosofi_text')
        if request.form.get('structure_text'):
            structure.text = request.form.get('structure_text')
        db.session.commit()

        temp = Partner.query.filter_by(name='temp').first()
        if request.files.get(f'partner_{temp.id}_photo'):
            image = request.files.get(f'partner_{temp.id}_photo')
            path = os.path.join('app/static/images/partner', '{}.jpg'.format(temp.id))
            image.save(path)
            compress_img(path, width=1920, height=1080)
            setattr(temp, 'name', f'{temp.id}')
            temp.link = request.form.get('partner_' + str(temp.id) + '_link')
            db.session.commit()
            return redirect(url_for('admin_panel.about'))

    partners = Partner.query.all()

    return render_template('admin_panel/about.html', filosofi=filosofi, about=about, structure=structure,
                           partners=partners)


@bp.route('/comments', methods=['GET'])
@login_required
def comments():
    comments = Comment.query.all()

    return render_template('admin_panel/comments.html', title='Отзывы',
                           comments=comments)


@bp.route('/edit_comment', methods=['GET', 'POST'])
@login_required
def edit_comment():
    comment = Comment.query.filter_by(id=request.args.get('comment_id')).first()

    if request.method == 'POST':
        name = request.form.get('name')
        text = request.form.get('text')

        setattr(comment, 'name', name)
        setattr(comment, 'text', text)

        try:
            if request.files.get('change'):
                image = request.files.get('change')
                path = os.path.join('app/static/images/comments', '{}.jpg'.format(comment.id))
                image.save(path)
                compress_img(path, width=1920, height=1080)
        except:
            pass

        db.session.commit()

        if request.form.get('delete'):
            db.session.delete(comment)
            db.session.commit()

            return redirect(url_for('admin_panel.comments'))

    return render_template('admin_panel/edit_comment.html', title='Отзывы',
                           comment=comment)


# создание отзыва
@bp.route('/comment_create', methods=['GET', 'POST'])
@login_required
def comment_create():
    if request.method == 'POST':
        name = request.form.get('name')
        text = request.form.get('text')

        comment = Comment(name=name, text=text)

        db.session.add(comment)
        db.session.commit()

        if request.files['photo']:
            photo = request.files['photo']
            try:
                path = os.path.join('app/static/images/comments', '{}.jpg'.format(
                    Comment.query.filter_by(name=name, text=text).first().id))
                photo.save(path)
                compress_img(path, width=1920, height=1080)
            except:
                pass

        return redirect(url_for('admin_panel.comments'))

    return render_template('admin_panel/comment_create.html', title='Создание отзыва')


@bp.route('/category_types', methods=['GET'])
@login_required
def category_types():
    category_types = Type.query.order_by(Type.number).all()

    return render_template('admin_panel/category_types.html', title='Группы категорий',
                           category_types=category_types)


@bp.route('/edit_category_type', methods=['GET', 'POST'])
@login_required
def edit_category_type():
    type = Type.query.filter_by(id=request.args.get('type_id')).first()
    categories = Category.query.all()

    if request.method == 'POST':
        name = request.form.get('name')
        number = request.form.get('number')

        setattr(type, 'name', name)
        setattr(type, 'number', number)

        db.session.commit()

        for category in categories:
            temp = CategoryType(type_id=type.id, category_id=category.id)

            if request.form.get(str(category.id)) == str(category.id):
                if not CategoryType.query.filter_by(type_id=type.id, category_id=category.id).first():
                    db.session.add(temp)
                    db.session.commit()
            else:
                temp = CategoryType.query.filter_by(type_id=type.id, category_id=category.id).first()
                if temp:
                    db.session.delete(temp)
                    db.session.commit()

        if request.form.get('delete'):
            db.session.delete(type)
            db.session.commit()

        return redirect(url_for('admin_panel.category_types'))

    categories_checked = [0]
    for category in categories:
        if CategoryType.query.filter_by(type_id=type.id, category_id=category.id).first():
            categories_checked.insert(category.id, category.id)
        else:
            categories_checked.insert(category.id, 0)

    return render_template('admin_panel/edit_type_category.html', title='Группа категорий',
                           type=type, categories=categories, categories_checked=categories_checked)


# создание отзыва
@bp.route('/category_type_create', methods=['GET', 'POST'])
@login_required
def category_type_create():
    if request.method == 'POST':
        name = request.form.get('name')
        number = request.form.get('number')

        type = Type(name=name, number=number)

        db.session.add(type)
        db.session.commit()

        type = Type.query.all()[-1]

        for category in Category.query.all():
            temp = CategoryType(type_id=type.id, category_id=category.id)

            if request.form.get(str(category.id)) == str(category.id):
                if not CategoryType.query.filter_by(type_id=type.id, category_id=category.id).first():
                    db.session.add(temp)
                    db.session.commit()
            else:
                temp = CategoryType.query.filter_by(type_id=type.id, category_id=category.id).first()
                if temp:
                    db.session.delete(temp)
                    db.session.commit()

        return redirect(url_for('admin_panel.category_types'))

    return render_template('admin_panel/category_type_create.html', title='Создание отзыва',
                           categories=Category.query.all())


@bp.route('/gallery', methods=['GET', 'POST'])
@login_required
def gallery():
    try:
        files = listdir('app/static/images/gallery')
        files.sort(key=lambda x: int(x[0:-4]))
    except:
        files = []
    if request.method == 'POST':
        for photo in files:
            if request.form.get('delete_' + str(photo)):
                try:
                    os.remove('app/static/images/gallery/' + str(photo))
                    return redirect(url_for('admin_panel.gallery'))
                except:
                    pass

        if request.files.get('add_photo'):
            images = request.files.getlist('add_photo')
            count = int(os.path.splitext(files[-1])[0])
            for img in images:
                path = os.path.join('app/static/images/gallery', '{}.jpg'.format(count + 1))
                img.save(path)
                compress_img(path, width=1920, height=1080, quality=70)
                count += 1

        return redirect(url_for('admin_panel.gallery'))

    return render_template('admin_panel/gallery.html', categories=get_categories(), images=files)


@bp.route('/contacts', methods=['GET', 'POST'])
@login_required
def contacts():
    contacts_info = Text.query.filter_by(title='contacts_info').first()

    if request.method == 'POST':
        if request.form.get('contacts_info_text'):
            contacts_info.text = request.form.get('contacts_info_text')
            db.session.commit()

        if request.files['map']:
            photo = request.files['map']
            try:
                path = os.path.join('app/static/images/staff/map.jpg')
                photo.save(path)
                compress_img(path, width=1920, height=1080, quality=95)
            except:
                pass

    return render_template('admin_panel/contacts.html', contacts_info=contacts_info, contacts_data=get_contacts_data())


@bp.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r
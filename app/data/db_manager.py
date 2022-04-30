from app import login_manager, db_session
from flask_login import current_user
from flask import send_file, render_template

from .users import User
from .files import File
from .messages import Message
from .friends import Friends
from . import config

import hashlib
import os
import uuid
import datetime


def my_render_template(*args, **kwargs):
    active_page = kwargs.get('active_page')
    page = active_page if active_page else '.'.join(args[0].split('.')[:-1])
    print('page', page)
    pages = ['cloud', 'messenger', 'premium', 'support', 'about']
    is_active_pages = [False] * len(pages)
    if page in pages:
        is_active_pages[pages.index(page)] = True
    return render_template(*args, **kwargs, login=current_user.is_authenticated, pages=is_active_pages)


def get_friends_for_user(user):
    db_sess = db_session.create_session()
    friends1 = db_sess.query(Friends.receiver_id).filter_by(sender_id=user.id, accept=True).all()
    friends2 = db_sess.query(Friends.sender_id).filter_by(receiver_id=user.id, accept=True).all()
    req = []
    for f_id in friends1 + friends2:
        user = db_sess.query(User).get(f_id)
        req.append(user)
    return req


def get_friend_requests(user):
    db_sess = db_session.create_session()
    requests = db_sess.query(Friends).filter_by(receiver_id=user.id, accept=False).all()
    req = []
    for r in requests:
        user = db_sess.query(User).get(r.sender_id)
        req.append([r.sender_id, user.name])
    return req


def add_friend(user1, user_2_name):
    db_sess = db_session.create_session()
    user2 = db_sess.query(User).filter_by(name=user_2_name).first()
    if not user2:
        return "Такого юзера нет"
    if user2 in get_friends_for_user(user1):
        return "Такой уже есть в друзьях"
    if user1 in get_friend_requests(user2):
        return "Ты уже отправил запрос"
    friends = Friends(sender_id=user1.id, receiver_id=user2.id)
    db_sess.add(friends)
    db_sess.commit()


def accept_req(sender_id, receiver_id):
    db_sess = db_session.create_session()
    r = db_sess.query(Friends).filter_by(sender_id=sender_id, receiver_id=receiver_id).first()
    if not r:
        return "такого запроса нет, взломай себе ...."
    r.accept = True
    db_sess.commit()


def decline_req(user1_id, user2_id):
    db_sess = db_session.create_session()
    r1 = db_sess.query(Friends).filter_by(sender_id=user1_id, receiver_id=user2_id).first()
    r2 = db_sess.query(Friends).filter_by(sender_id=user2_id, receiver_id=user1_id).first()
    if not r1 and not r2:
        return "такого запроса нет, взломай себе ...."
    if not r1:
        db_sess.delete(r2)
    else:
        db_sess.delete(r1)
    db_sess.commit()


def get_messages_for_users(user1_id, user2_id):
    db_sess = db_session.create_session()
    messages1 = db_sess.query(Message).filter_by(sender_id=user1_id, receiver_id=user2_id).all()
    messages2 = db_sess.query(Message).filter_by(sender_id=user2_id, receiver_id=user1_id).all()
    messages = list(set(messages1 + messages2))
    messages = sorted(messages, key=lambda m: m.sent_date)
    return messages


def add_message(m, id1, id2):
    db_sess = db_session.create_session()
    mes = Message(text=m, sender_id=id2, receiver_id=id1)
    db_sess.add(mes)
    db_sess.commit()


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


def login_user(name, password):
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter_by(name=name).first()
    if user is not None:
        key_from_db, salt = user.password, user.salt
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=128)
        if key_from_db == key:
            return user
    return None


def add_new_user(form: dict) -> str:
    name = form['Login']
    email = form['Email']
    password = form['Password']
    repeat_password = form['RepeatPassword']

    error_message = check_incorrect_data(name, password, repeat_password)
    if error_message:
        return error_message

    user = User().with_password(password)
    user.name, user.email = name, email
    try:
        db_sess = db_session.create_session()
        db_sess.add(user)
        db_sess.commit()
    except Exception as e:
        print('ERROR ADD REGISTERED USER TO DB')
        print(e.__class__.__name__)
        print(e)
        return 'Не удалось создать аккаунт. Повторите попытку позднее'
    return ''


def normalize_filename(filename):
    symbols_to_remove = '{}%^:#!@"&*?/|\\<>,`~$;+' + "'"
    for i in symbols_to_remove:
        filename = filename.replace(i, '')
    if not filename:
        filename = 'unknown name'
    return filename


def save_file(request):
    file = request.files['File']

    path = uuid.uuid4().hex
    while os.path.exists(path):
        path = uuid.uuid4().hex
    
    filename = normalize_filename(file.filename)

    file.save(os.path.join(config.files_path, path))
    file = File(name=filename, path=path, date=datetime.date.today())
    db_sess = db_session.create_session()
    db_sess.add(file)
    user = db_sess.query(User).filter_by(id=current_user.id).first()
    user.add_file(file.id)
    db_sess.commit()
    return file.path


def remove_file(user, file_path):
    db_sess = db_session.create_session()
    file = db_sess.query(File).filter_by(path=file_path).first()
    db_sess.close()
    if file.id not in user.get_files():
        return
    try:
        os.remove(os.path.join(config.files_path, file.path))
    except FileNotFoundError:
        print(f'Файл {file.path} не существует')
    user.remove_file(file.id)
    db_sess.delete(file)
    db_sess.commit()


def download_file(user, file_path):
    db_sess = db_session.create_session()
    file = db_sess.query(File).filter_by(path=file_path).first()
    db_sess.close()
    print('file is open = ', file.is_open)
    if not file or not user:
        return
    if not (file.is_open or user.is_authenticated and file.id in user.get_files() + user.get_given_files()):
        return
    full_file_path = os.path.join(config.shorts_files_path, file.path)
    print('download', full_file_path)
    return send_file(full_file_path, download_name=file.name, as_attachment=True)


def find_file(user, file_path):
    db_sess = db_session.create_session()
    file = db_sess.query(File).filter_by(path=file_path).first()
    db_sess.close()
    if not file or not user or not (file.id in user.get_files() + user.get_given_files()):
        return
    print(file.name, 'is', bool(file.desc))
    return file


def edit_file(file_path, form):
    db_sess = db_session.create_session()
    file = db_sess.query(File).filter_by(path=file_path).one()
    file.name = normalize_filename(form['name'])
    file.desc = form['desc']
    file.is_open = int(form['access'])
    db_sess.commit()


def get_files_for(user):
    if not user.files:
        return []
    db_sess = db_session.create_session()
    return db_sess.query(File).filter(File.id.in_(user.get_files())).all()


def name_in_db(name: str):
    db_sess = db_session.create_session()
    return name.lower() in map(lambda x: x.name.lower(), db_sess.query(User).all())


def check_incorrect_data(name: str, password: str, repeat_password: str) -> str:
    if len(name) < 4:
        return 'Логин должен состоять из более чем 4 символов'
    if len(name) > 32:
        return 'Максимальный размер логина - 32 символа'
    if not name.isalnum():
        return 'Имя не должно содержать спец.символов'
    if name_in_db(name):
        return 'Пользователь с таким логином уже существует'
    if len(password) < 4:
        return 'Пароль должен состоять из более чем 4 символов'
    if len(name) > 100:
        return 'Максимальный размер пароля - 100 символов'
    if password != repeat_password:
        return 'Пароли не совпадают'
    return ''


def index_revert(path: str):
    for num, i in reversed(tuple(enumerate(path))):
        if i == '(':
            return num


def is_numbered(path):
    return path.endswith(')') and '(' in path and path[index_revert(path) + 1:-1].isnumeric()


def add_numbered(path):
    number = 1
    ext = ''
    if '.' in path:
        ext = '.' + path.split('.')[-1]
        path = '.'.join(path.split('.')[:-1])
    if is_numbered(path):
        number = int(path[index_revert(path) + 1:-1]) + 1
        path = path[:index_revert(path)]
    return path + f'({number}){ext}'

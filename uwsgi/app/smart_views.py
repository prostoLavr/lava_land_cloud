from . import app, server_name
from .data import db_manager
from .data.db_manager import my_render_template

from flask_login import login_required, login_user, current_user, logout_user
from flask import request, redirect


@app.route('/logout/')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/cloud')
def cloud():
    if not current_user.is_authenticated:
        return redirect('/')
    files = db_manager.get_files_for(current_user)
    return my_render_template('cloud.html', files=files)


@app.route('/load', methods=['GET', 'POST'])
def load():
    if request.method == 'POST':
        path_to_file = db_manager.save_file(request)
        return redirect(f'/edit_file/{path_to_file}')
    return my_render_template('load.html', active_page='cloud')


@app.route('/remove/<string:file_path>')
@login_required
def remove(file_path):
    db_manager.remove_file(current_user, file_path)
    return redirect('/cloud')


@app.route('/download/<string:file_path>')
def download(file_path):
    res = db_manager.download_file(current_user, file_path)
    if res is None:
        return redirect('/file_not_found')
    return res


@app.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect('/cloud')
    if request.method == 'POST':
        error_message = db_manager.add_new_user(request.form)
        if error_message:
            return my_render_template('register.html', message=error_message)
        else:
            return my_render_template('success_register.html')
    else:
        return my_render_template('register.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    message = ''
    if current_user.is_authenticated:
        return redirect('/cloud')
    if request.method == 'POST':
        username = request.form.get('Login')
        password = request.form.get('Password')
        user = db_manager.login_user(username, password)
        if user is not None:
            login_user(user)
            return redirect('/cloud')
        else:
            message = 'Неверный логин или пароль'
    return my_render_template('login.html', message=message)


@app.route('/messenger/accept_req/<string:user_id>')
@login_required
def accept_req(user_id):
    res = db_manager.accept_req(user_id, current_user.id)
    if res is None:
        pass
    return redirect('/messenger')


@app.route('/messenger/decline_req/<string:user_id>')
@login_required
def decline_req(user_id):
    res = db_manager.decline_req(user_id, current_user.id)
    if res is None:
        pass
    return redirect('/messenger')


@app.route('/messenger', methods=['POST', 'GET'])
def messenger():
    if current_user.is_anonymous:
        return redirect('/')
    mes = None
    if request.method == 'POST':
        friend_name = request.form.get('Friend_Login')
        m = db_manager.add_friend(current_user, friend_name)
        if m:
            mes = m
    user_friends = db_manager.get_friends_for_user(current_user)
    user_requests = db_manager.get_friend_requests(current_user)
    return my_render_template('messenger.html', users=user_friends,
                              req=user_requests, message=mes)


@app.route('/messenger/<user_id>', methods=['POST', 'GET'])
@login_required
def chat(user_id):
    friends = db_manager.get_friends_for_user(current_user)
    if db_manager.load_user(user_id) not in friends:
        return redirect('/messenger')
    if request.method == 'POST':
        message = request.form['message']
        db_manager.add_message(message, user_id, current_user.id)
    messages = db_manager.get_messages_for_users(current_user.id, user_id)
    user_friend = db_manager.load_user(user_id)
    return my_render_template('chat.html', messages=messages, friend=user_friend, active_page='messanger')


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect('/cloud')
    return my_render_template('index.html')


@app.route('/account')
def account():
    if current_user.is_anonymous:
        return redirect('/')
    # return my_render_template('account.html')
    return my_render_template('no_work.html')


@app.route('/edit_file/<file_path>', methods=['POST', 'GET'])
def edit_file(file_path):
    if request.method == 'POST':
        print(request.form)
        db_manager.edit_file(file_path, request.form)
        return redirect('/cloud')
    file_to_edit = db_manager.find_file(current_user, file_path)
    if not file_to_edit:
        return redirect('/file_not_found')
    return my_render_template('file.html', file=file_to_edit, link=f'https://{server_name}/download/{file_to_edit.path}')
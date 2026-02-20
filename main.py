from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'xD'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123@localhost/voting'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Модели
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Voting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    options = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    creator = db.relationship('User', backref='votings')

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voting_id = db.Column(db.Integer, db.ForeignKey('voting.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    selected_option = db.Column(db.Integer, nullable=False)
    
    __table_args__ = (db.UniqueConstraint('voting_id', 'user_id'),)

# Создание таблиц
with app.app_context():
    db.create_all()
    
    # Создаем тестового админа если нет пользователей
    if not User.query.first():
        admin = User(login='admin', email='admin@mail.com', password=generate_password_hash('admin123'), is_admin=True)
        db.session.add(admin)
        db.session.commit()

# Главная
@app.route('/')
def index():
    votings = Voting.query.filter_by(is_active=True).all()
    return render_template('index.html', votings=votings)

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        email = request.form['email']
        
        if User.query.filter_by(login=login).first():
            flash('Логин уже существует', 'error')
            return redirect(url_for('register'))
        
        new_user = User(login=login, email=email)
        new_user.password = generate_password_hash(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        
        user = User.query.filter_by(login=login).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['login'] = user.login
            session['is_admin'] = user.is_admin
            flash('Вход выполнен', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

# Выход
@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли', 'info')
    return redirect(url_for('index'))

# Создание голосования
@app.route('/create', methods=['GET', 'POST'])
def create_voting():
    if 'user_id' not in session:
        flash('Сначала войдите', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        options = request.form.getlist('options')
        options = [opt for opt in options if opt.strip()]
        
        if len(options) < 2:
            flash('Нужно минимум 2 варианта', 'error')
            return redirect(url_for('create_voting'))
        
        new_voting = Voting(
            creator_id=session['user_id'],
            title=title,
            description=description
        )
        new_voting.options = json.dumps(options)
        
        db.session.add(new_voting)
        db.session.commit()
        
        flash('Голосование создано', 'success')
        return redirect(url_for('index'))
    
    return render_template('create_voting.html')

# Просмотр голосования
@app.route('/voting/<int:voting_id>')
def view_voting(voting_id):
    voting = Voting.query.get_or_404(voting_id)
    options = json.loads(voting.options)
    
    user_voted = False
    if 'user_id' in session:
        user_voted = Vote.query.filter_by(voting_id=voting_id, user_id=session['user_id']).first() is not None
    
    # Результаты
    results = {}
    total_votes = Vote.query.filter_by(voting_id=voting_id).count()
    
    for i, option in enumerate(options):
        votes_count = Vote.query.filter_by(voting_id=voting_id, selected_option=i).count()
        percentage = (votes_count / total_votes * 100) if total_votes > 0 else 0
        results[option] = {
            'votes': votes_count,
            'percentage': round(percentage, 1)
        }
    
    return render_template('voting.html', 
                         voting=voting, 
                         options=options,
                         results=results,
                         user_voted=user_voted,
                         total_votes=total_votes)

# Голосование
@app.route('/voting/<int:voting_id>/vote', methods=['POST'])
def vote(voting_id):
    if 'user_id' not in session:
        flash('Сначала войдите', 'error')
        return redirect(url_for('login'))
    
    voting = Voting.query.get_or_404(voting_id)
    
    if not voting.is_active:
        flash('Голосование завершено', 'error')
        return redirect(url_for('view_voting', voting_id=voting_id))
    
    existing = Vote.query.filter_by(voting_id=voting_id, user_id=session['user_id']).first()
    if existing:
        flash('Вы уже голосовали', 'error')
        return redirect(url_for('view_voting', voting_id=voting_id))
    
    option = request.form.get('option')
    if option is None:
        flash('Выберите вариант', 'error')
        return redirect(url_for('view_voting', voting_id=voting_id))
    
    new_vote = Vote(
        voting_id=voting_id,
        user_id=session['user_id'],
        selected_option=int(option)
    )
    
    db.session.add(new_vote)
    db.session.commit()
    
    flash('Голос учтен!', 'success')
    return redirect(url_for('view_voting', voting_id=voting_id))

# Управление (для админа)
@app.route('/manage')
def manage_votings():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    votings = Voting.query.all()
    return render_template('manage_votings.html', votings=votings)

# Завершение голосования
@app.route('/voting/<int:voting_id>/close')
def close_voting(voting_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    voting = Voting.query.get_or_404(voting_id)
    voting.is_active = False
    db.session.commit()
    
    flash('Голосование завершено', 'success')
    return redirect(url_for('manage_votings'))

# Удаление голосования
@app.route('/voting/<int:voting_id>/delete')
def delete_voting(voting_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    voting = Voting.query.get_or_404(voting_id)
    Vote.query.filter_by(voting_id=voting_id).delete()
    db.session.delete(voting)
    db.session.commit()
    
    flash('Голосование удалено', 'success')
    return redirect(url_for('manage_votings'))

if __name__ == '__main__':
    app.run(debug=True)
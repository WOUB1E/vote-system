import unittest
import json
from main import app, db, User, Voting, Vote
from werkzeug.security import generate_password_hash

class VotingAppTestCase(unittest.TestCase):

    def setUp(self):
        """Настройка перед каждым тестом"""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret'
        self.app = app.test_client()
        
        with app.app_context():
            db.create_all()
            # Создаем тестового админа
            admin = User(
                login='adminn', 
                email='admin@test.com', 
                password=generate_password_hash('admin123'), 
                is_admin=True
            )
            # Создаем обычного пользователя
            user = User(
                login='user_test', 
                email='user@test.com', 
                password=generate_password_hash('user123'), 
                is_admin=False
            )
            db.session.add_all([admin, user])
            db.session.commit()

    def tearDown(self):
        """Очистка базы после каждого теста"""
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # 1. Создание нового пользователя
    def test_registration_success(self):
        response = self.app.post('/register', data=dict(
            login='newbie', password='password123', email='new@test.com'
        ), follow_redirects=True)
        self.assertIn('Регистрация успешна!', response.get_data(as_text=True))

    # 2. Создание пользователя с неверными данными (дубликат логина)
    def test_registration_fail_duplicate(self):
        response = self.app.post('/register', data=dict(
            login='user_test', password='123', email='user@test.com'
        ), follow_redirects=True)
        self.assertIn('Логин уже существует', response.get_data(as_text=True))

    # 3. Вход с неверными данными
    def test_login_fail(self):
        response = self.app.post('/login', data=dict(
            login='user_test', password='wrongpass'
        ), follow_redirects=True)
        self.assertIn('Неверный логин или пароль', response.get_data(as_text=True))

    # 4. Вход с верными данными
    def test_login_success(self):
        response = self.app.post('/login', data=dict(
            login='user_test', password='user123'
        ), follow_redirects=True)
        self.assertIn('Вход выполнен', response.get_data(as_text=True))

    # 5. Доступ к /manage без прав админа
    def test_manage_access_denied(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 2  # user_test
            sess['is_admin'] = False
        response = self.app.get('/manage', follow_redirects=True)
        self.assertIn('Доступ запрещен', response.get_data(as_text=True))

    # 6. Доступ к /manage с правами админа
    def test_manage_access_granted(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1  # admin_test
            sess['is_admin'] = True
        response = self.app.get('/manage')
        self.assertEqual(response.status_code, 200)

    # 7. Создание голосования
    def test_create_voting(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['is_admin'] = True
        
        response = self.app.post('/create', data={
            'title': 'Test',
            'description': 'disc',
            'options': ['A', 'B']
        }, follow_redirects=True)
        self.assertIn('Голосование создано', response.get_data(as_text=True))

    # 8. Создание голоса
    def test_create_vote(self):
        with app.app_context():
            v = Voting(creator_id=1, title="VoteTest", options=json.dumps(['A', 'B']))
            db.session.add(v)
            db.session.commit()
            v_id = v.id

        with self.app.session_transaction() as sess:
            sess['user_id'] = 2
        
        response = self.app.post(f'/voting/{v_id}/vote', data={'option': '0'}, follow_redirects=True)
        self.assertIn('Голос учтен!', response.get_data(as_text=True))

    # 9. Повторное голосование
    def test_double_vote_fail(self):
        with app.app_context():
            v = Voting(creator_id=1, title="Double", options=json.dumps(['A', 'B']))
            db.session.add(v)
            db.session.commit()
            v_id = v.id

        with self.app.session_transaction() as sess:
            sess['user_id'] = 2

        # Первый голос
        self.app.post(f'/voting/{v_id}/vote', data={'option': '0'})
        # Повторный голос
        response = self.app.post(f'/voting/{v_id}/vote', data={'option': '1'}, follow_redirects=True)
        self.assertIn('Вы уже голосовали', response.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main(verbosity=2)
from django.contrib.auth.models import User
from django.test import TestCase, override_settings


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('member', 'Member@example.com', 'Test-password-42')

    def test_username_and_email_sign_in(self):
        for identifier in ('member', 'Member@example.com', ' MEMBER@EXAMPLE.COM '):
            with self.subTest(identifier=identifier):
                self.client.logout()
                response = self.client.post('/login/', {'username': identifier, 'password': 'Test-password-42'})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_wrong_password_and_unknown_email_fail(self):
        for identifier in ('member', 'Member@example.com', 'missing@example.com'):
            response = self.client.post('/login/', {'username': identifier, 'password': 'wrong'})
            self.assertContains(response, 'Please enter a correct username or email and password.')
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()
        self.client.post('/login/', {'username': self.user.email, 'password': 'Test-password-42'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_duplicate_email_requires_username(self):
        User.objects.create_user('other', 'member@example.com', 'Other-password-42')
        self.client.post('/login/', {'username': 'member@example.com', 'password': 'Test-password-42'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_email_shaped_username_takes_precedence(self):
        user = User.objects.create_user('Member@example.com', password='Separate-password-42')
        self.client.post('/login/', {'username': user.username, 'password': 'Separate-password-42'})
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_login_label(self):
        self.assertContains(self.client.get('/login/'), 'Username or email')

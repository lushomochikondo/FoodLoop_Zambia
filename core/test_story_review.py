from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from .models import NewsArticle, Notification, Organisation, StorySubmission


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StoryReviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('reviewer', password='Test-password-42')
        self.author = User.objects.create_user('author', password='Test-password-42')
        org = Organisation.objects.create(name='Community Kitchen', role='recipient', status='approved', area='Lusaka')
        self.story = StorySubmission.objects.create(organisation=org, submitted_by=self.author, title='Community meal', summary='A donation supported our programme.', body='Our community kitchen received food.', consent_confirmed=True)
        self.url = f'/admin/core/storysubmission/{self.story.pk}/change/'
        self.client.force_login(self.admin)

    def test_review_page_has_publish_and_decline_buttons(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Publish success story')
        self.assertContains(response, 'Decline story')

    def test_publish_saves_note_and_publishes_once(self):
        for _ in range(2):
            response = self.client.post(self.url, {'review_note':'Reviewed with permission', '_publish_story':'Publish success story'})
            self.assertEqual(response.status_code, 302)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'published')
        self.assertEqual(self.story.review_note, 'Reviewed with permission')
        self.assertEqual(NewsArticle.objects.count(), 1)
        self.assertTrue(self.story.news_article.published)
        self.assertEqual(Notification.objects.filter(user=self.author).count(), 1)
        self.assertNotContains(self.client.get(self.url), 'name="_publish_story"')

    def test_decline_saves_feedback_without_publishing(self):
        self.client.post(self.url, {'review_note':'Please remove identifiable details.', '_decline_story':'Decline story'})
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'declined')
        self.assertFalse(NewsArticle.objects.exists())
        self.assertTrue(Notification.objects.filter(user=self.author, message__contains='Please remove identifiable details.').exists())

    def test_non_admin_cannot_publish(self):
        self.client.force_login(self.author)
        self.client.post(self.url, {'_publish_story':'Publish success story'})
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'pending')
        self.assertFalse(NewsArticle.objects.exists())

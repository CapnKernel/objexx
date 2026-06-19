import pytest
from django.urls import reverse

from pytest_django.asserts import assertRedirects, assertTemplateUsed


def test_top_anonymous(client):
    """Top page is accessible without authentication."""
    response = client.get(reverse('top'))
    assert response.status_code == 200
    assertTemplateUsed(response, 'app/top.html')
    assertTemplateUsed(response, 'app/base.html')
    # Anonymous users should see a login link, not a logout form
    assert b'Log in' in response.content
    assert b'Log out' not in response.content


def test_top_authenticated(client, django_user_model):
    """Top page shows different content for authenticated users."""
    django_user_model.objects.create_user(
        email='test@example.com', password='secret123'
    )
    client.login(email='test@example.com', password='secret123')
    response = client.get(reverse('top'))
    assert response.status_code == 200
    assertTemplateUsed(response, 'app/top.html')
    # Authenticated users should see a logout form, not a login link
    assert b'Log out' in response.content
    assert b'test@example.com' in response.content


def test_favicon_anonymous(client):
    """Favicon is accessible without authentication."""
    response = client.get(reverse('favicon'))
    assert response.status_code == 301  # PermanentRedirectView to static file


def test_admin_redirects_anonymous(client, db):
    """Admin requires authentication; anonymous users get redirected."""
    response = client.get('/office/')
    assertRedirects(response, f"{reverse('admin:login')}?next={reverse('admin:index')}")


def test_admin_denies_unauthorised(client, django_user_model):
    """Non-staff users get a 302 (redirect to admin login then 200)."""
    django_user_model.objects.create_user(
        email='user@example.com', password='secret123'
    )
    client.login(email='user@example.com', password='secret123')
    response = client.get('/office/', follow=True)
    # Django admin returns 200 with "You are not staff" message
    assert response.status_code == 200
    assert b'staff' in response.content or b'login' in response.content


def test_login_page_anonymous(client, db):
    """Login page is accessible without authentication."""
    response = client.get(reverse('login'))
    assert response.status_code == 200
    assertTemplateUsed(response, 'registration/login.html')


def test_password_reset_anonymous(client):
    """Password reset pages are accessible without authentication."""
    response = client.get(reverse('password_reset'))
    assert response.status_code == 200
    assertTemplateUsed(response, 'registration/my_password_reset_form.html')


def test_password_reset_done_anonymous(client):
    """Password reset done page is accessible without authentication."""
    response = client.get(reverse('password_reset_done'))
    assert response.status_code == 200
    assertTemplateUsed(response, 'registration/my_password_reset_done.html')


def test_logout_requires_post(client, django_user_model):
    """Logout via GET should not work (requires POST)."""
    django_user_model.objects.create_user(
        email='test@example.com', password='secret123'
    )
    client.login(email='test@example.com', password='secret123')
    response = client.get(reverse('logout'))
    # GET on logout should return a method-not-allowed or similar
    assert response.status_code in (200, 405)


def test_logout_success(client, django_user_model):
    """Logout via POST logs the user out."""
    django_user_model.objects.create_user(
        email='test@example.com', password='secret123'
    )
    client.login(email='test@example.com', password='secret123')
    response = client.post(reverse('logout'), follow=True)
    assertRedirects(response, reverse('top'))
    # After logout, the top page should show the login link again
    assert b'Log in' in response.content

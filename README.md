Check out this repo to kickstart a Django project.

Next step: The steps from "Create your Django app" onwards:

  https://brntn.me/blog/six-things-i-do-every-time-i-start-a-django-project/


```
cd pyproj/
python3 -m venv env
. env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
sed -i "3c\SECRET_KEY = \"$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')\"" .env
vi .env  # Set DEPLOY_TYPE

cp conf/local_settings.py.template conf/local_settings.py
vi conf/local_settings.py  # Remove top or bottom half depending on DEPLOY_TYPE

./manage.py migrate
./manage.py createsuperuser
./manage.py startapp app

vi pyproj/settings.py  # Add 'app' to INSTALLED_APPS

```

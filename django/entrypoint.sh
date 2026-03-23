set -e

python manage.py migrate

if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
  python manage.py createsuperuser --noinput || true
fi

python manage.py runserver 0.0.0.0:8000


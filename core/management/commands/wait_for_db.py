import time
import logging
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """Django command to pause execution until database is available"""
    help = 'Waits for the database to become available.'

    def handle(self, *args, **options):
        self.stdout.write('Waiting for database...')
        db_conn = None
        retries = 30
        while retries > 0:
            try:
                db_conn = connections['default']
                db_conn.cursor() # Try to establish a connection
                self.stdout.write(self.style.SUCCESS('Database available!'))
                break
            except OperationalError:
                self.stdout.write('Database unavailable, waiting 1 second...')
                retries -= 1
                time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error connecting to database: {e}")
                self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
                retries -= 1
                time.sleep(1)

        if db_conn is None or retries == 0:
            self.stderr.write(self.style.ERROR('Database unavailable after waiting.'))
            exit(1) 
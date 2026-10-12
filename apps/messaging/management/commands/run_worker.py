import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.messaging.services import work_once

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process inbound messages and due reminders until stopped (SIGINT/SIGTERM)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Exit when there is no work left.")
        parser.add_argument("--poll", type=float, default=0.5, help="Idle sleep in seconds.")

    def handle(self, *args, once: bool, poll: float, **options):
        stopping = False

        def stop(signum, frame):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        self.stdout.write("worker started")

        # The current unit of work always finishes before a stop takes effect.
        while not stopping:
            try:
                worked = work_once()
            except Exception:
                if once:
                    raise
                # Unexpected (e.g. the database went away): log, reconnect, keep going.
                log.exception("worker iteration failed")
                close_old_connections()
                time.sleep(poll)
                continue
            if not worked:
                if once:
                    break
                close_old_connections()
                time.sleep(poll)
        self.stdout.write("worker stopped")

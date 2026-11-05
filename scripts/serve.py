"""Launch the production server; migrations are a separate release command."""
import os

port = int(os.environ.get('PORT', '8000'))
if not 1 <= port <= 65535:
    raise ValueError('PORT must be between 1 and 65535.')
args = ['gunicorn', 'config.wsgi:application', '--bind', f'0.0.0.0:{port}', '--workers', os.environ.get('WEB_CONCURRENCY', '2'), '--timeout', '60', '--access-logfile', '-', '--error-logfile', '-']
os.execvp(args[0], args)

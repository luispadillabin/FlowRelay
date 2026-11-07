"""Loopback-only learning server for fictional webhook events."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from relay import Queue, ValidationError, ConflictError

MAX_BODY = 16384
STATIC = Path(__file__).parent / 'static'


def handler_for(queue):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Avoid putting payloads or request URLs into logs.

        def reply(self, status, data):
            body = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.headers_common(len(body))
            self.wfile.write(body)

        def headers_common(self, length):
            self.send_header('Content-Length', str(length))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/health':
                return self.reply(200, {'status': 'ok', 'mode': 'local-simulation'})
            if path == '/api/events':
                return self.reply(200, queue.list())
            if path.startswith('/api/events/'):
                result = queue.detail(unquote(path[len('/api/events/'):]))
                return self.reply(200 if result else 404, result or {'error': 'Event not found'})
            files = {'/': 'index.html', '/app.js': 'app.js', '/styles.css': 'styles.css'}
            if path not in files:
                return self.reply(404, {'error': 'Not found'})
            file = STATIC / files[path]
            body = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[file.suffix[1:]] + '; charset=utf-8')
            self.headers_common(len(body))
            self.wfile.write(body)

        def do_POST(self):
            # Reject browser cross-origin writes, even though this server is loopback only.
            origin = self.headers.get('Origin')
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if origin and origin != expected:
                return self.reply(403, {'error': 'Cross-origin writes are disabled'})
            path = urlsplit(self.path).path
            if path not in ('/api/events', '/api/process'):
                return self.reply(404, {'error': 'Not found'})
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValidationError('Transfer-Encoding is unsupported.')
                if self.headers.get_content_type() != 'application/json':
                    return self.reply(415, {'error': 'Use Content-Type: application/json'})
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= length <= MAX_BODY:
                    return self.reply(413, {'error': 'Body must be at most 16 KiB with Content-Length'})
                self.connection.settimeout(5)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValidationError('Incomplete request body.')
                def unique(pairs):
                    result = {}
                    for k, v in pairs:
                        if k in result:
                            raise ValidationError('Duplicate JSON keys are not allowed.')
                        result[k] = v
                    return result
                data = json.loads(raw, object_pairs_hook=unique,
                                  parse_constant=lambda _: (_ for _ in ()).throw(ValidationError('Non-finite numbers are invalid.')))
                if path == '/api/process':
                    if data != {}:
                        raise ValidationError('Send an empty object to process the next due event.')
                    return self.reply(200, {'processed': queue.process()})
                event, created = queue.submit(data)
                return self.reply(201 if created else 200, {'event': event, 'created': created})
            except ConflictError as exc:
                self.reply(409, {'error': str(exc)})
            except (ValueError, UnicodeError, RecursionError, TimeoutError) as exc:
                self.reply(400, {'error': str(exc) if isinstance(exc, ValidationError) else 'Invalid request JSON or body.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', default=str(Path(__file__).parent / 'flowrelay.db'))
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(Queue(args.db)))
    print(f'FlowRelay: http://127.0.0.1:{server.server_port} — Ctrl+C to stop', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

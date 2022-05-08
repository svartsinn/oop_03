import json
import logging
import uuid

from api import method_handler
import redis.exceptions

from constants import *
from store import RedisStore, RedisCache
from optparse import OptionParser

from http.server import HTTPServer, BaseHTTPRequestHandler


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler,
    }
    store = RedisStore(RedisCache())

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        logging.debug(f'Context: {context}')
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            logging.debug(f'Data string receiving: {data_string}')
            request = json.loads(data_string)
            logging.info(f'Request: {request}')
        except Exception as err:
            logging.error(err)
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    code, response = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except KeyError:
                    logging.error('Incorrect API method')
                    code = INVALID_REQUEST
                except redis.exceptions.ConnectionError as err:
                    logging.error(f'Connection error to Redis: {err}')
                    code = INTERNAL_ERROR
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode('utf-8'))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()

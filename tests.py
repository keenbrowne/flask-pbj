import unittest
import flask
from flask_pbj import api, json, protobuf
from json import dumps, loads
from werkzeug.exceptions import (
    BadRequest,
    NotAcceptable,
    UnsupportedMediaType
)
from test_pb import Person

# TODO:
# Empty data (both in requests and returned from view method)
# More tests combining both json and protobuf
# More complex dictionaries with lists and nested data
# test copy* methods directly

class TestJson(unittest.TestCase):
    def test_simple_json_request(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            data=dumps(data),
            method='POST',
            content_type="application/json",
            headers={
                "Accept": "*/*"
            }
        ):
            @api(json)
            def view_method():
                self.assertEqual(flask.request.data_dict, data)
                return 200

            view_method()

    def test_simple_json_response(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            method='GET',
            content_type="application/json",
            headers={
                "Accept": "*/*"
            }
        ):
            @api(json)
            def view_method():
                return data

            response, status_code, headers = view_method()

        self.assertEquals(loads(response.data), data)
        self.assertEquals(response.mimetype, 'application/json')
        self.assertEquals(status_code, 200)

    def test_bad_content_type(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            method='POST',
            content_type="application/x-plist",
            headers={
                "Accept": "application/json"
            }
        ):
            @api(json)
            def view_method():
                return data
            with self.assertRaises(UnsupportedMediaType):
                response, status_code, headers = view_method()

    def test_bad_accept(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            method='GET',
            content_type="application/json",
            headers={
                "Accept": "application/x-plist"
            }
        ):
            @api(json)
            def view_method():
                return data
            with self.assertRaises(NotAcceptable):
                response, status_code, headers = view_method()

    def test_missing_data(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            data=dumps(data),
            method='POST',
            content_type="application/json",
            headers={
                "Accept": "application/json"
            }
        ):
            @api(json)
            def view_method():
                with self.assertRaises(BadRequest):
                    flask.request.data_dict['b']

    def test_malformed_data(self):
        app = flask.Flask(__name__)
        with app.test_request_context(
            data="this data is malformed because it is not a json object literal.",
            method='POST',
            content_type="application/json",
            headers={
                "Accept": "application/json"
            }
        ):
            @api(json)
            def view_method():
                pass
            with self.assertRaises(BadRequest):
                view_method()

class TestProtobuf(unittest.TestCase):
    def test_simple_pb_request(self):
        data = Person()
        data.id = 1
        data.name = "tester"
        data.email = "tester@example.com"

        app = flask.Flask(__name__)
        with app.test_request_context(
            data=data.SerializeToString(),
            method='POST',
            content_type="application/x-protobuf",
            headers={
                "Accept": "application/x-protobuf"
            }
        ):
            @api(protobuf(receives=Person))
            def view_method():
                self.assertEqual(flask.request.data_dict, {'id': 1, 'name': 'tester', 'email': 'tester@example.com'})
                return 200

            view_method()

    def test_simple_pb_response(self):
        person = Person()
        person.id = 1
        person.name = "tester"
        person.email = "tester@example.com"

        data = {
            "id": person.id,
            "name": person.name,
            "email": person.email
        }

        app = flask.Flask(__name__)

        with app.test_request_context(
            method='GET',
            content_type="application/x-protobuf",
            headers={
                "Accept": "application/x-protobuf"
            }
        ):
            @api(protobuf(sends=Person))
            def view_method():
                return data

            response, status_code, headers = view_method()

        response_data = Person()
        response_data.ParseFromString(response.data)

        self.assertEquals(response_data, person)
        self.assertEquals(response.mimetype, 'application/x-protobuf')
        self.assertEquals(status_code, 200)

    def test_bad_content_type(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            method='POST',
            content_type="application/x-plist",
            headers={
                "Accept": "application/x-protobuf"
            }
        ):
            @api(protobuf(receives=Person))
            def view_method():
                return data
            with self.assertRaises(UnsupportedMediaType):
                response, status_code, headers = view_method()

    def test_bad_accept(self):
        data = {'a': 1}
        app = flask.Flask(__name__)
        with app.test_request_context(
            method='GET',
            content_type="application/x-protobuf",
            headers={
                "Accept": "application/x-plist"
            }
        ):
            @api(protobuf(sends=Person))
            def view_method():
                return data
            with self.assertRaises(NotAcceptable):
                response, status_code, headers = view_method()

    def test_malformed_data(self):
        app = flask.Flask(__name__)
        with app.test_request_context(
            data="this data is malformed because it is not a protobuf binary.",
            method='POST',
            content_type="application/x-protobuf",
            headers={
                "Accept": "application/x-protobuf"
            }
        ):
            @api(protobuf(receives=Person))
            def view_method():
                pass
            with self.assertRaises(BadRequest):
                view_method()


class TestPbj(unittest.TestCase):
    def test_json_favored(self):
        data = Person()
        data.id = 1
        data.name = "tester"
        data.email = "tester@example.com"

        response_data = {
            "id": data.id,
            "name": data.name,
            "email": data.email
        }

        app = flask.Flask(__name__)
        with app.test_request_context(
            data=data.SerializeToString(),
            method='POST',
            content_type="application/x-protobuf",
            headers={
                "Accept": "*/*"
            }
        ):
            @api(json, protobuf(receives=Person))
            def view_method():
                return flask.request.data_dict

            response, status_code, headers = view_method()

        self.assertEquals(response.status_code, 200)
        self.assertEquals(loads(response.data), response_data)
        self.assertEquals(response.mimetype, "application/json")


if __name__ == "__main__":
    unittest.main()

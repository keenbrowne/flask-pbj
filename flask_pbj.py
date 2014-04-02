# -*- coding: utf-8 -*-
'''
    flask.ext.pbj
    ---------------

    This module provides support for protobuf and json formatted request and
    response data.

    :copyright: (c) 2014 by Keen Browne.
    :license: MIT/X11, see LICENSE for more details.
'''

__version_info__ = ('0', '1', '0')
__version__ = ".".join(__version_info__)
__author__ = "Keen Browne"
__license__ = "MIT/X11"
__copyright__ = "(c) 2014 by Keen Browne"
__all__ = ['api', 'json', 'protobuf']

from functools import wraps

from flask import abort, jsonify, request, Flask

from google.protobuf.internal.containers import BaseContainer
from google.protobuf.reflection import GeneratedProtocolMessageType
from google.protobuf.message import Message as ProtocolMessage, DecodeError

from werkzeug.wrappers import Response


class EncodeError(Exception):
    pass


class PbjRequest(Flask.request_class):
    def __init__(self, *args, **kwargs):
        super(PbjRequest, self).__init__(*args, **kwargs)
        self.data_dict = None

Flask.request_class = PbjRequest


# TODO: consider using the word 'decode' and 'encode' instead of copy
def copy_dict_to_pb(instance, dictionary):
    """
        Copy the key, value pairs in a dictionary to the fields of an instance
        of a protobuf message. This method assumes that key values in the
        dictionary correspond to field names in the message. Enums are not well
        supported.
    """
    assert(isinstance(dictionary, dict))
    for key, value in dictionary.iteritems():
        if value is None:
            continue
        # If the value is another dictionary set the field to the values
        # in the nested dictionary
        if isinstance(value, dict):
            attribute = getattr(instance, key)
            copy_dict_to_pb(attribute, value)
        # If the value is iterable, copy the list into the repeated field
        elif hasattr(value, "__iter__"):
            attribute = getattr(instance, key)
            if len(value) == 0 or not isinstance(value[0], dict):
                attribute.extend(value)
            else:
                for item in value:
                    copy_dict_to_pb(attribute.add(), item)
        # Otherwise the value is a basic type, so set the field directly
        else:
            setattr(instance, key, value)


def copy_pb_to_dict(dictionary, instance):

    for descriptor, value in instance.ListFields():
        # If the field is another Protobuf Message, make a new dictionary
        # and copy the messages fields
        if isinstance(value, ProtocolMessage):
            dictionary[descriptor.name] = {}
            copy_pb_to_dict(dictionary[descriptor.name], value)
        # If the field is repeated, create a list and copy the repeated field
        # values into the dictionary
        elif isinstance(value, BaseContainer):
            dictionary[descriptor.name] = []
            for item in value:
                if isinstance(item, ProtocolMessage):
                    dict_item = {}
                    copy_pb_to_dict(dict_item, item)
                    dictionary[descriptor.name].append(dict_item)
                else:
                    dictionary[descriptor.name].append(item)
        # Otherwise the field value is just a basic type and should be set
        # on the dict.
        else:
            dictionary[descriptor.name] = value


def _result_to_response_tuple(result):
    # Returned tuples are also evaluated
    if isinstance(result, tuple):
        assert(len(result) > 0 and len(result) <= 3)
        if (len(result) == 1):
            return result[0], 200, {}
        if (len(result) == 2):
            return result[0], result[1], {}
        elif (len(result) == 3):
            return result

    return result, 200, {}


class JsonDictKeyError(KeyError):
    pass


class JsonResponseDict(dict):
    def __getitem__(self, key):
        try:
            return super(JsonResponseDict, self).__getitem__(key)
        except KeyError:
            raise JsonDictKeyError(key)


class JsonCodec(object):
    mimetype = "application/json"

    def parse_request_data(self, _request):
        return JsonResponseDict(_request.get_json())

    def make_response(self, data, status_code, headers):
        response = jsonify(**data)
        return response, status_code, headers


class ProtobufCodec(object):
    mimetype = "application/x-protobuf"

    def __init__(self, sends=None, receives=None, errors=None):
        assert(sends or receives)
        if sends:
            assert(isinstance(sends, GeneratedProtocolMessageType))
        if receives:
            assert(isinstance(receives, GeneratedProtocolMessageType))
        if errors:
            assert(isinstance(errors, GeneratedProtocolMessageType))

        self.send_type = sends
        self.receive_type = receives
        self.error_type = errors

    def parse_request_data(self, _request):
        if not self.receive_type:
            abort(400)  # Bad Request
        data_dict = {}
        message = self.receive_type()
        try:
            message.ParseFromString(_request.data)
        except DecodeError:
            abort(400)
        copy_pb_to_dict(data_dict, message)

        return data_dict

    def make_response(self, data, status_code, headers):
        if not data:
            Flask.response_class(
                "",
                mimetype=self.mimetype
            ), status_code, headers

        # if the status code is not a success code
        if status_code % 100 == 4 and self.error_type:
            response_data = self.error_type()
        else:
            if not self.send_type:
                raise EncodeError(
                    "Data could not be encoded into a protobuf message. No "
                    "protobuf message type specified to send."
                )
            response_data = self.send_type()

        copy_dict_to_pb(
            instance=response_data,
            dictionary=data
        )

        return Flask.response_class(
            response_data.SerializeToString(),
            mimetype=self.mimetype
        ), status_code, headers

json = JsonCodec()
protobuf = ProtobufCodec


class api(object):
    """Convert request and response data between python dictionaries and the
    provided formats.

    The view method can access the added request.data_dict data member for
    input and return a dictionary for output. The client's accept and
    content-type headers determine the format of the messages.

    Similar to flask, routes can avoid pbj.api's response serialization by
    directly returning a flask.Response object.

    Example:
        example_messages.proto
        message Person {
            required int32 id = 1;
            required string name = 2;
            optional string email = 3;
        }

        message Team {
            required int32 id = 1;
            required string name = 2;
            required Person leader = 3
            repeated Person members = 4;
        }

        app.py
        @app.route('/teams', methods=['POST'])
        @api(json, protobuf(receives=Person, sends=Team))
        def create_team():
            # Given a team leader return a new team
            leader = request.data_dict
            return {
                'id': get_url(2),
                'name': "{0}'s Team".format(leader['name']),
                'leader': get_url(person[id]),
                'members': [],
            }

        Create a team with JSON:
        curl -X POST -H "Accept: application/json" \
            -H "Content-type: application/json" \
            http://127.0.0.1:5000/teams --data {'id': 1, 'name': 'Red Leader'}
        {
            "id": 2,
            "name": "Red Leader's Team",
            "leader": "/people/1"
            "members": []
        }

        Create a new team with google protobuf:
        # Create and save a Person structure in python
        from example_messages_pb2 import Person
        leader = Person()
        leader.id = 1
        leader.name = 'Red Leader'
        with open('person.pb', 'wb') as f:
            f.write(leader.SerializeToString())

        curl -X POST -H "Accept: application/x-protobuf" \
            -H "Content-type: application/x-protobuf" \
            http://127.0.0.1:5000/teams --data-binary @person.pb > team.pb
    """
    def __init__(self, *codecs):
        self.codecs = dict([(codec.mimetype, codec) for codec in codecs])
        self.mimetypes = [
            codec.mimetype for codec in codecs
        ]

    def parse_request_data(self, _request):
        """
        For PUT and POST requests, convert message into a dictionary which can
        be used by app.route functions.
        """
        if _request.method in ('POST', 'PUT'):
            if _request.content_type in self.mimetypes:
                codec = self.codecs[_request.content_type]
                return codec.parse_request_data(_request)
            else:
                abort(415)  # Unsupported media type

    def response_mimetype(self, _request):
        # Do we support this mimetype?
        # Will the method return a message?
        # if the method won't return a message, can we use another mimetype?
        return _request.accept_mimetypes.best_match(
            self.mimetypes
        )

    def __call__(self, fn):
        @wraps(fn)
        def to_response(*args, **kwargs):

            request.data_dict = self.parse_request_data(request)
            try:
                result = fn(*args, **kwargs)
            except JsonDictKeyError:
                abort(400)

            # Similar to flask's app.route, returned werkzeug responses are
            # passed directly back to the caller
            if isinstance(result, Response):
                return result

            # If the view method returns a default flask-style tuple throw
            # an error as when making rest API's the view method more likely
            # to return dicts and status codes than strings and headres
            if (isinstance(result, tuple) and (
                len(result) == 0 or
                not isinstance(result[0], dict)
            )):
                raise EncodeError(
                    "Pbj does not support flask's default tuple format "
                    "of (response, headers) or (response, headers, "
                    "status_code). Either return an instance of "
                    "flask.response_class to override pbj's response "
                    "encoding or return a tuple of (dict, status_code) "
                    "or (dict, status_code, headers)."
                )

            # Verify the server can respond to the client using
            # a mimetype the client accepts. We check after calling because
            # of the nature of Http 406
            mimetype = self.response_mimetype(request)
            if not mimetype:
                abort(406)  # Not Acceptable

            # If result is just an int, it must be a status code, so return
            # the response with no data and a status code
            if isinstance(result, int):
                return Flask.response_class("", mimetype=mimetype), result, []

            data, status_code, headers = _result_to_response_tuple(result)

            if not isinstance(data, dict):
                raise EncodeError(
                    "Methods decorated with api must return a dict, int "
                    "status code or flask Response."
                )

            return self.codecs[mimetype].make_response(
                data,
                status_code,
                headers
            )

        return to_response

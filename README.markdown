# Flask Peanut Butter & Jelly
Flask-Pbj provides support for [Google Protocol Buffers](https://developers.google.com/protocol-buffers/docs/overview)
and json formatted request and response data. The api decorator serializes 
and deserializes json or protobuf formatted messages to and from a python 
dictionary.

## Why Flask-Pbj
Flask Peanut Butter and Jelly to simplifies the creation of REST APIs for C++ 
clients. Flask-pbj decorated app.routes accept and return protobuf messages or
JSON. The JSON is useful for debugging and public API's while Google Protobuf 
is a well-documented compact and efficient format, particularly useful for 
C++/Python communication.

## Examples
*example_messages.proto*
```
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
```
*app.py*
```python
# The route function can access the added request.data_dict data member for
# input and return a dictionary for output. The client's accept and
# content-type headers determine the format of the messages.
# Similar to flask, routes can avoid pbjs response serialization by directly
# returning a flask.Response object.
@app.route('/teams', methods=['POST'])
@api(json, protobuf(receives=Person, sends=Team, errors=Error))
def create_team():
    leader = request.data_dict
 
    if len(leader['name']) < 3:
        # Optionally, return a tuple of the form dict, status_code, headers
        # A 4xx HTTP error will use the 'errors' protobuf message type
        return {"errorMessage": "Name too short"}, 400

    # For a 200 response, just return a dict
    return {
        'id': get_url(2),
        'name': "{0}'s Team".format(leader['name']),
        'leader': get_url(person[id]),
        'members': [],
    }
```
*Create a team with JSON:*
```
curl -X POST -H "Accept: application/json" \
    -H "Content-type: application/json" \
    http://127.0.0.1:5000/teams --data {'id': 1, 'name': 'Red Leader'}
{
    "id": 2,
    "name": "Red Leader's Team",
    "leader": "/people/1"
    "members": []
}
```
*Create a new team with google protobuf:*
```python
# Create and save a Person structure in python
from example_messages_pb2 import Person
leader = Person()
leader.id = 1
leader.name = 'Red Leader'
with open('person.pb', 'wb') as f:
    f.write(leader.SerializeToString())
```
```
curl -X POST -H "Accept: application/x-protobuf" \
    -H "Content-type: application/x-protobuf" \
    http://127.0.0.1:5000/teams --data-binary @person.pb > team.pb
```

## Adding new mimetypes
Codecs are classes see JsonCodec and ProtobufCodec for examples

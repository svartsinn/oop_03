#!/usr/bin/env python
# -*- coding: utf-8 -*-
import hashlib
import logging
from datetime import datetime

from constants import *
from fields import Field, CharField, ArgumentsField, EmailField, PhoneField, DateField, \
    BirthDayField, GenderField, ClientIDsField
from scoring import get_score, get_interests


class RequestMeta(type):
    def __new__(mcs, name, bases, attributes):
        fields = {}
        for key, val in attributes.items():
            if isinstance(val, Field):
                fields[key] = val

        cls = super().__new__(mcs, name, bases, attributes)
        cls.fields = fields
        return cls


class Request(metaclass=RequestMeta):

    def __init__(self, request_params, validation=True):
        self.errors = []
        for name, field in self.fields.items():
            value = request_params[name] if name in request_params else None
            try:
                if validation:
                    field.validate(value)
                setattr(self, name, value)
            except ValueError as e:
                self.errors.append(f'field "{name}": {str(e)}')

    def is_valid(self):
        return not self.errors


class ClientsInterestsRequest(Request):
    client_ids = ClientIDsField(required=True, nullable=False)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(Request):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def __init__(self, request_params):
        super().__init__(request_params)
        if not self.is_valid():
            return

        for first_pair, second_pair in self.get_valid_field_pairs():
            if getattr(self, first_pair) is not None and getattr(self, second_pair) is not None:
                return

        self.errors.append('there are no valid pairs')

    @staticmethod
    def get_valid_field_pairs():
        return [
            ['phone', 'email'],
            ['first_name', 'last_name'],
            ['gender', 'birthday']
        ]

    def get_not_empty_fields(self):
        result = []
        for name in self.fields:
            if getattr(self, name) is not None:
                result.append(name)
        return result


class MethodRequest(Request):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request: MethodRequest):
    if request.is_admin:
        digest = hashlib.sha512((datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).
                                encode("utf-8")).hexdigest()
    else:
        digest = hashlib.sha512((request.account + request.login + SALT).
                                encode("utf-8")).hexdigest()
    logging.info(f'Hash for {request.login} is {digest}')
    if digest == request.token:
        return True
    return False


def method_handler(request, ctx, store):
    method_request = MethodRequest(request['body'])
    if not method_request.is_valid():
        return method_request.errors, INVALID_REQUEST
    if not check_auth(method_request):
        return ERRORS[FORBIDDEN], FORBIDDEN
    return process_scoring(method_request, ctx, store)


def process_scoring(method_request, ctx, store):
    method_name = method_request.method
    if not method_name:
        return ERRORS[INVALID_REQUEST], INVALID_REQUEST

    scoring_methods = {
        'online_score': get_online_score,
        'clients_interests': get_clients_interests
    }
    try:
        method = scoring_methods[method_name]
    except KeyError:
        return ERRORS[FORBIDDEN], FORBIDDEN

    return method(method_request, ctx, store)


def get_online_score(method_request, ctx, store):
    if method_request.is_admin:
        return  {'score': int(ADMIN_SALT)}, OK
    request = OnlineScoreRequest(method_request.arguments)
    if not request.is_valid():
        return request.errors, INVALID_REQUEST
    ctx['has'] = request.get_not_empty_fields()

    score = get_score(store, request.phone, request.email, request.birthday, request.gender,
                      request.first_name, request.last_name)
    return {'score': score}, OK


def get_clients_interests(method_request, ctx, store):
    request = ClientsInterestsRequest(method_request.arguments)
    if not request.is_valid():
        return request.errors, INVALID_REQUEST
    client_ids = request.client_ids
    ctx['nclients'] = len(client_ids)
    clients_interests = {}
    for cid in client_ids:
        clients_interests[cid] = get_interests(store, cid)
    return clients_interests, OK

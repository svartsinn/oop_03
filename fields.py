import collections
import logging
from datetime import datetime

from constants import UNKNOWN, MALE, FEMALE


class ValidationError(ValueError):
    pass


class Field:
    def __init__(self, required=False, nullable=True):
        self.required = required
        self.nullable = nullable

    def validate(self, value):
        if self.required and value is None:
            raise ValidationError('value is required')
        if not self.nullable and self.is_nullable(value):
            raise ValidationError('value can not be null')

    @staticmethod
    def is_nullable(value):
        return len(value) == 0 if isinstance(value, collections.Iterable) else value is None


class CharField(Field):
    def validate(self, value):
        logging.debug('validating chars')
        super().validate(value)
        if not value:
            return
        if not isinstance(value, str):
            raise ValidationError('invalid value type')


class ListField(Field):
    def validate(self, value):
        logging.debug('validating list')
        if not isinstance(value, list):
            raise ValidationError('List Field got non-list type')


class DictField(Field):
    def validate(self, value):
        logging.debug('List validating')
        if not isinstance(value, dict):
            raise ValidationError('Dict field got non-dict type')


class ArgumentsField(DictField):
    def validate(self, value):
        super().validate(value)
        if not isinstance(value, dict):
            raise ValidationError('invalid value type')


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if not value:
            return
        if '@' not in value:
            raise ValidationError('invalid value format')


class PhoneField(CharField):
    def validate(self, value):
        logging.debug('Validating phone number')
        if not value:
            return
        value = str(value)
        super().validate(value)
        if len(value) != 11:
            raise ValidationError('Phone number not contain 11 symbols')
        elif not value.isdigit():
            raise ValidationError('Phone number contain non-digits')
        elif not value.startswith('7'):
            raise ValidationError('Phone number not starts with 7')


class DateField(CharField):
    def validate(self, value):
        super().validate(value)
        if not value:
            return
        try:
            datetime.strptime(value, '%d.%m.%Y')
        except ValueError:
            raise ValidationError('invalid value format')


class BirthDayField(DateField):
    def validate(self, value):
        logging.debug('Validating birthday date')
        super().validate(value)
        if not value:
            return
        value = datetime.strptime(value, "%d.%m.%Y").date()
        today = datetime.now().date()
        if today.year - value.year > 70:
            raise ValidationError('Current age more than 70 years')


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if not value:
            return
        if not isinstance(value, int):
            raise ValidationError('invalid field type')
        if value not in [UNKNOWN, MALE, FEMALE]:
            raise ValidationError('invalid field value')


class ClientIDsField(Field):
    def validate(self, value):
        super().validate(value)
        if not isinstance(value, list):
            raise ValidationError('value must be list type')
        for clientId in value:
            if not isinstance(clientId, int):
                raise ValidationError('clientId must be integer type')

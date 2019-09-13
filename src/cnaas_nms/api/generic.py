import re

from flask import request
import sqlalchemy


FILTER_RE = re.compile(r"^filter\[([a-zA-Z0-9_.]+)\](\[[a-z]+\])?$")


def limit_results() -> int:
    """Find number of results to limit query to, either by user requested
    param or a default value."""
    limit = 10

    args = request.args
    if 'limit' in args:
        try:
            r_limit = int(args['limit'])
            limit = max(1, min(100, r_limit))
        except:
            pass

    return limit


def build_filter(f_class, query):
    """Generate SQLalchemy filter based on query string and return
    filtered query.
    Raises:
        ValueError
    """
    args = request.args
    for arg, value in args.items():
        match = re.match(FILTER_RE, arg)
        if not match or len(match.groups()) != 2:
            continue
        attribute = match.groups()[0].replace('.', '_')
        operator = match.groups()[1]
        if operator:
            operator = operator.lstrip('[').rstrip(']')

        if attribute not in f_class.__table__._columns.keys():
            raise ValueError("{} is not a valid attribute to filter on".format(attribute))
        # Special handling from Enum type, check valid enum names
        if isinstance(f_class.__table__._columns[attribute].type, sqlalchemy.Enum):
            value = value.upper()
            allowed_names = set(item.name for item in \
                                f_class.__table__._columns[attribute].type.enum_class)
            if value not in allowed_names:
                raise ValueError("{} is not a valid value for {}".format(
                    value, attribute
                ))
        f_class_field = getattr(f_class, attribute)
        if operator == 'contains':
            f_class_op = getattr(f_class_field, 'contains')
        else:
            f_class_op = getattr(f_class_field, '__eq__')

#        kwargs = {attribute: value}
        query = query.filter(f_class_op(value))

    return query


def empty_result(status='success', data=None):
    if status == 'success':
        return {
            'status': status,
            'data': data
        }
    elif status == 'error':
        return {
            'status': status,
            'message': data if data else "Unknown error"
        }

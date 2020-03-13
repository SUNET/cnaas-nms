import re

from flask import request
import sqlalchemy


FILTER_RE = re.compile(r"^filter\[([a-zA-Z0-9_.]+)\](\[[a-z]+\])?$")
DEFAULT_PER_PAGE = 50


def limit_results() -> int:
    """Find number of results to limit query to, either by user requested
    param or a default value."""
    limit = DEFAULT_PER_PAGE

    args = request.args
    if 'per_page' in args:
        try:
            per_page_arg = int(args['per_page'])
            limit = max(1, min(100, per_page_arg))
        except:
            pass

    return limit


def offset_results() -> int:
    """Find number of results to offset query to, either by user requested
    param or a default value."""
    offset = 0
    per_page = DEFAULT_PER_PAGE

    args = request.args
    if 'per_page' in args:
        try:
            per_page_arg = int(args['per_page'])
            per_page = max(1, min(100, per_page_arg))
        except:
            pass

    if 'page' in args:
        try:
            page_arg = int(args['page'])
            offset = (max(1, page_arg) - 1) * per_page
        except:
            pass

    return offset


def build_filter(f_class, query: sqlalchemy.orm.query.Query):
    """Generate SQLalchemy filter based on query string and return
    filtered query.
    Raises:
        ValueError
    """
    args = request.args
    f_class_order_by_field = None
    order = None  # sqlalchemy asc or desc
    for arg, value in args.items():
        match = re.match(FILTER_RE, arg)
        if arg == 'sort' and isinstance(value, str):
            order_by_field = value.lower()
            if order_by_field.startswith('-'):
                order_by_field = order_by_field.lstrip('-')
                order = sqlalchemy.desc
            else:
                order = sqlalchemy.asc

            if order_by_field in f_class.__table__._columns.keys():
                f_class_order_by_field = getattr(f_class, order_by_field)
            continue
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

        query = query.filter(f_class_op(value))

    if f_class_order_by_field:
        query = query.order_by(order(f_class_order_by_field))
    else:
        if 'id' in f_class.__table__._columns.keys():
            order = sqlalchemy.asc
            f_class_order_by_field = getattr(f_class, 'id')
            query = query.order_by(order(f_class_order_by_field))
    query = query.limit(limit_results())
    query = query.offset(offset_results())
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

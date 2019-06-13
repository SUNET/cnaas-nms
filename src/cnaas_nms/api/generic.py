from flask import request
import sqlalchemy


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
    if not 'filter' in args:
        return query
    split = args['filter'].split(',')
    if not len(split) == 2:
        # invalid
        return query
    attribute, value = split
    if not attribute in f_class.__table__._columns.keys():
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

    kwargs = {attribute: value}
    return query.filter_by(**kwargs)


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

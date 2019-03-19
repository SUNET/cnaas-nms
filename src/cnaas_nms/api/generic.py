from flask import request


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
    args = request.args
    if not 'filter' in args:
        return query
    split = args['filter'].split(',')
    if not len(split) == 2:
        # invalid
        return query
    attribute, value = split
    if not attribute in f_class.__table__._columns.keys():
        # invalid
        return query
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

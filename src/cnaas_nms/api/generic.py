import math
import re
import urllib
from typing import List

import sqlalchemy
from flask import request

from cnaas_nms.db.settings import get_pydantic_error_value, get_pydantic_field_descr

FILTER_RE = re.compile(r"^filter\[([a-zA-Z0-9_.]+)\](\[[a-z]+\])?$")
DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 1000


def limit_results() -> int:
    """Find number of results to limit query to, either by user requested
    param or a default value."""
    limit = DEFAULT_PER_PAGE

    args = request.args
    if "per_page" in args:
        try:
            per_page_arg = int(args["per_page"])
            assert 1 <= per_page_arg <= MAX_PER_PAGE
            limit = per_page_arg
        except (AssertionError, ValueError):
            raise ValueError("per_page argument must be integer between 1-{}".format(MAX_PER_PAGE))

    return limit


def offset_results() -> int:
    """Find number of results to offset query to, either by user requested
    param or a default value."""
    offset = 0
    per_page = DEFAULT_PER_PAGE

    args = request.args
    if "per_page" in args:
        try:
            per_page_arg = int(args["per_page"])
            assert 1 <= per_page_arg <= MAX_PER_PAGE
            per_page = per_page_arg
        except (AssertionError, ValueError):
            raise ValueError("per_page argument must be integer between 1-{}".format(MAX_PER_PAGE))

    if "page" in args:
        try:
            page_arg = int(args["page"])
            offset = (max(1, page_arg) - 1) * per_page
        except Exception:  # noqa: F401
            pass

    return offset


def pagination_headers(total_count) -> dict:
    per_page = DEFAULT_PER_PAGE
    page_arg = 1
    links = []
    headers = {
        "X-Total-Count": total_count,
    }

    args = request.args
    if "per_page" in args:
        try:
            per_page_arg = int(args["per_page"])
            assert 1 <= per_page_arg <= MAX_PER_PAGE
            per_page = per_page_arg
        except (AssertionError, ValueError):
            pass

    last_page = math.ceil(total_count / per_page)
    if last_page == 1:
        return headers

    if "page" in args:
        try:
            page_arg = max(1, int(args["page"]))
        except ValueError:
            pass

    query = request.args

    if page_arg < last_page:
        links.append(
            '<{}>; rel="next"'.format(request.base_url + "?" + urllib.parse.urlencode({**query, "page": page_arg + 1}))
        )
        links.append(
            '<{}>; rel="last"'.format(request.base_url + "?" + urllib.parse.urlencode({**query, "page": last_page}))
        )

    if links:
        headers["Link"] = ",".join(links)

    return headers


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
        if arg == "sort" and isinstance(value, str):
            order_by_field = value.lower()
            if order_by_field.startswith("-"):
                order_by_field = order_by_field.lstrip("-")
                order = sqlalchemy.desc
            else:
                order = sqlalchemy.asc

            if order_by_field in f_class.__table__._columns.keys():
                f_class_order_by_field = getattr(f_class, order_by_field)
            continue
        if not match or len(match.groups()) != 2:
            continue
        attribute = match.groups()[0].replace(".", "_")
        operator = match.groups()[1]
        if operator:
            operator = operator.lstrip("[").rstrip("]")

        if attribute not in f_class.__table__._columns.keys():
            raise ValueError("{} is not a valid attribute to filter on".format(attribute))
        # Special handling from Enum type, check valid enum names
        allowed_names = None
        if isinstance(f_class.__table__._columns[attribute].type, sqlalchemy.Enum):
            value = value.upper()
            allowed_names = set(item.name for item in f_class.__table__._columns[attribute].type.enum_class)
            if value not in allowed_names:
                raise ValueError("{} is not a valid value for {}".format(value, attribute))
        f_class_field = getattr(f_class, attribute)
        if operator == "contains":
            if allowed_names:
                raise ValueError("Cannot use 'contains' operator for enum types")
            if isinstance(f_class.__table__._columns[attribute].type, sqlalchemy.Integer):
                raise ValueError("Cannot use 'contains' operator for integer types")
            if isinstance(f_class.__table__._columns[attribute].type, sqlalchemy.DateTime):
                raise ValueError("Cannot use 'contains' operator for datetime types")
            f_class_op = getattr(f_class_field, "ilike")
            value = "%" + value + "%"
        else:
            f_class_op = getattr(f_class_field, "__eq__")

        query = query.filter(f_class_op(value))

    if f_class_order_by_field:
        query = query.order_by(order(f_class_order_by_field))
    else:
        if "id" in f_class.__table__._columns.keys():
            order = sqlalchemy.asc
            f_class_order_by_field = getattr(f_class, "id")
            query = query.order_by(order(f_class_order_by_field))
    query = query.limit(limit_results())
    query = query.offset(offset_results())
    return query


def empty_result(status="success", data=None):
    if status == "success":
        return {"status": status, "data": data}
    elif status == "error":
        return {"status": status, "message": data if data else "Unknown error"}


def parse_pydantic_error(e: Exception, schema, data: dict) -> List[str]:
    errors = []
    for num, error in enumerate(e.errors()):
        loc = error["loc"]
        errors.append(
            "Validation error for setting {}, bad value: {}".format(
                "->".join(str(x) for x in loc), get_pydantic_error_value(data, loc)
            )
        )
        try:
            pydantic_descr = get_pydantic_field_descr(schema.model_json_schema(), loc)
            if pydantic_descr:
                pydantic_descr_msg = ", field should be: {}".format(pydantic_descr)
            else:
                pydantic_descr_msg = ""
        except Exception:  # noqa: S110
            pydantic_descr_msg = ""
        errors.append("Message: {}{}".format(error["msg"], pydantic_descr_msg))
    return errors


def update_sqla_object(instance, new_data: dict) -> bool:
    """Update SQLalchemy object instance with data dict.
    Returns:
        Returns True if any values were changed
    """
    changed = False
    for k, v in new_data.items():
        if k == "id":  # Don't allow updating of instance id
            continue
        try:
            if getattr(instance, k) != v:
                setattr(instance, k, v)
                changed = True
        except AttributeError:
            continue
    return changed

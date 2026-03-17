"""Framework-agnostic filtering and pagination utilities for FastAPI endpoints.

These parallel the Flask-dependent functions in generic.py but accept explicit
parameters instead of reading from flask.request.
"""

import math
import re
import urllib.parse
from typing import Any, Dict

import sqlalchemy
from sqlalchemy.orm import Query

FILTER_RE = re.compile(r"^filter\[([a-zA-Z0-9_.]+)\](\[[a-z]+\])?$")


def build_filter(
    f_class: Any,
    query: Query,
    args: Dict[str, str],
    per_page: int = 50,
    page: int = 1,
) -> Query:
    """Generate SQLAlchemy filter from query params dict and return filtered query.

    Args:
        f_class: SQLAlchemy model class
        query: Base SQLAlchemy query
        args: Dict of query string parameters (e.g. from request.query_params)
        per_page: Results per page (1-1000)
        page: Page number (1-based)

    Raises:
        ValueError: If filter attribute or value is invalid
    """
    f_class_order_by_field = None
    order = None

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

    if f_class_order_by_field and order:
        query = query.order_by(order(f_class_order_by_field))
    else:
        if "id" in f_class.__table__._columns.keys():
            order = sqlalchemy.asc
            f_class_order_by_field = getattr(f_class, "id")
            query = query.order_by(order(f_class_order_by_field))

    query = query.limit(per_page)
    query = query.offset((max(1, page) - 1) * per_page)
    return query


def pagination_headers(
    total_count: int,
    args: Dict[str, str],
    per_page: int = 50,
    page: int = 1,
    base_url: str = "",
) -> Dict[str, Any]:
    """Build pagination headers (X-Total-Count, Link).

    Args:
        total_count: Total number of results
        args: Dict of query string parameters
        per_page: Results per page
        page: Current page number (1-based)
        base_url: Base URL for Link header construction
    """
    links = []
    headers: Dict[str, Any] = {
        "X-Total-Count": str(total_count),
    }

    last_page = math.ceil(total_count / per_page) if per_page > 0 else 1
    if last_page <= 1:
        return headers

    page = max(1, page)

    if page < last_page:
        links.append(
            '<{}>; rel="next"'.format(base_url + "?" + urllib.parse.urlencode({**args, "page": page + 1}))
        )
        links.append(
            '<{}>; rel="last"'.format(base_url + "?" + urllib.parse.urlencode({**args, "page": last_page}))
        )

    if links:
        headers["Link"] = ",".join(links)

    return headers

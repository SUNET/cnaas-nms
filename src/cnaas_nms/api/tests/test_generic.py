"""Unit tests for generic.py and the framework-agnostic filtering/response utilities."""

import unittest
from unittest.mock import MagicMock

from pydantic import BaseModel, ValidationError

from cnaas_nms.api.filtering import build_filter, pagination_headers
from cnaas_nms.api.generic import empty_result, parse_pydantic_error, update_sqla_object
from cnaas_nms.api.response import empty_result as fastapi_empty_result


class TestEmptyResult(unittest.TestCase):
    def test_success_with_data(self):
        result = empty_result(status="success", data={"key": "value"})
        assert result == {"status": "success", "data": {"key": "value"}}

    def test_success_with_none(self):
        result = empty_result(status="success", data=None)
        assert result == {"status": "success", "data": None}

    def test_error_with_message(self):
        result = empty_result(status="error", data="Something went wrong")
        assert result == {"status": "error", "message": "Something went wrong"}

    def test_error_with_none(self):
        result = empty_result(status="error", data=None)
        assert result == {"status": "error", "message": "Unknown error"}

    def test_unknown_status(self):
        result = empty_result(status="unknown")
        assert result == {}


class TestFastapiEmptyResult(unittest.TestCase):
    """Verify the FastAPI response helper produces identical output."""

    def test_success_with_data(self):
        result = fastapi_empty_result(status="success", data={"key": "value"})
        assert result == {"status": "success", "data": {"key": "value"}}

    def test_error_with_message(self):
        result = fastapi_empty_result(status="error", data="Something went wrong")
        assert result == {"status": "error", "message": "Something went wrong"}

    def test_error_with_none(self):
        result = fastapi_empty_result(status="error", data=None)
        assert result == {"status": "error", "message": "Unknown error"}

    def test_unknown_status(self):
        result = fastapi_empty_result(status="unknown")
        assert result == {}


class TestUpdateSqlaObject(unittest.TestCase):
    def test_update_changes_attributes(self):
        obj = MagicMock()
        obj.name = "old"
        obj.value = 1
        changed = update_sqla_object(obj, {"name": "new", "value": 2})
        assert changed is True
        assert obj.name == "new"
        assert obj.value == 2

    def test_no_change_returns_false(self):
        obj = MagicMock()
        obj.name = "same"
        changed = update_sqla_object(obj, {"name": "same"})
        assert changed is False

    def test_id_field_is_skipped(self):
        obj = MagicMock()
        obj.id = 1
        obj.name = "old"
        changed = update_sqla_object(obj, {"id": 999, "name": "new"})
        assert changed is True
        assert obj.id == 1  # id should not be changed

    def test_nonexistent_attribute_is_skipped(self):
        obj = MagicMock(spec=["name"])
        obj.name = "old"
        # MagicMock with spec will raise AttributeError for non-existent attrs
        changed = update_sqla_object(obj, {"nonexistent": "value"})
        assert changed is False


class TestParsePydanticError(unittest.TestCase):
    def test_parse_validation_error(self):
        class TestModel(BaseModel):
            name: str
            age: int

        try:
            TestModel(name=123, age="not_a_number")  # type: ignore
        except ValidationError as e:
            errors = parse_pydantic_error(e, TestModel, {"name": 123, "age": "not_a_number"})
            assert len(errors) > 0
            assert any("age" in err for err in errors)


class TestPaginationHeaders(unittest.TestCase):
    def test_single_page(self):
        headers = pagination_headers(total_count=10, args={}, per_page=50, page=1, base_url="http://test/api")
        assert headers["X-Total-Count"] == "10"
        assert "Link" not in headers

    def test_multiple_pages(self):
        headers = pagination_headers(total_count=100, args={}, per_page=10, page=1, base_url="http://test/api")
        assert headers["X-Total-Count"] == "100"
        assert "Link" in headers
        assert 'rel="next"' in headers["Link"]
        assert 'rel="last"' in headers["Link"]
        assert "page=2" in headers["Link"]
        assert "page=10" in headers["Link"]

    def test_last_page_no_next(self):
        headers = pagination_headers(total_count=100, args={}, per_page=10, page=10, base_url="http://test/api")
        assert headers["X-Total-Count"] == "100"
        assert "Link" not in headers

    def test_preserves_existing_args(self):
        headers = pagination_headers(
            total_count=100,
            args={"filter[name]": "test"},
            per_page=10,
            page=1,
            base_url="http://test/api",
        )
        assert "filter%5Bname%5D=test" in headers["Link"]

    def test_zero_results(self):
        headers = pagination_headers(total_count=0, args={}, per_page=50, page=1, base_url="http://test/api")
        assert headers["X-Total-Count"] == "0"
        assert "Link" not in headers


class TestBuildFilter(unittest.TestCase):
    """Test build_filter with a mock SQLAlchemy model."""

    def _make_mock_model(self, include_id: bool = True):
        """Create a mock SQLAlchemy model class with a table-like structure."""
        import sqlalchemy

        mock_model = MagicMock()
        mock_model.__table__ = MagicMock()

        columns = ["hostname", "state"]
        if include_id:
            columns.insert(0, "id")
        mock_model.__table__._columns.keys.return_value = columns

        id_col = MagicMock()
        id_col.type = sqlalchemy.Integer()
        hostname_col = MagicMock()
        hostname_col.type = sqlalchemy.String()
        state_col = MagicMock()
        state_col.type = sqlalchemy.String()

        col_map = {"id": id_col, "hostname": hostname_col, "state": state_col}
        mock_model.__table__._columns.__getitem__ = lambda self, key: col_map[key]

        return mock_model

    def test_empty_args_no_id(self):
        """Test build_filter with no args and no id column (skips order_by)."""
        mock_model = self._make_mock_model(include_id=False)
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query

        build_filter(mock_model, mock_query, {})
        mock_query.limit.assert_called_once_with(50)
        mock_query.offset.assert_called_once_with(0)

    def test_invalid_filter_attribute(self):
        mock_model = self._make_mock_model()
        mock_query = MagicMock()

        with self.assertRaises(ValueError) as ctx:
            build_filter(mock_model, mock_query, {"filter[invalid_col]": "test"})
        assert "not a valid attribute" in str(ctx.exception)

    def test_pagination_params_no_id(self):
        """Test pagination with explicit per_page/page, no id column."""
        mock_model = self._make_mock_model(include_id=False)
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query

        build_filter(mock_model, mock_query, {}, per_page=10, page=3)
        mock_query.limit.assert_called_once_with(10)
        mock_query.offset.assert_called_once_with(20)


if __name__ == "__main__":
    unittest.main()

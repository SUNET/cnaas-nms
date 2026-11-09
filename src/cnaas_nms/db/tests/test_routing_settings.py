import pytest
from pydantic import ValidationError

from cnaas_nms.db.settings_fields.routing import f_routing


def test_routing_policy_set_attributes():
    attributes = [
        {"set_type": "local-preference", "set_target": "200"},
        {"set_type": "metric", "set_target": "50"},
    ]
    routing = f_routing.model_validate(
        {
            "routing_policies": {
                "example": {"statements": [{"action": "accept", "conditions": [], "set_attributes": attributes}]}
            }
        }
    )

    assert routing.model_dump()["routing_policies"]["example"]["statements"][0]["set_attributes"] == attributes


def test_routing_policy_omitted_set_attributes():
    routing = f_routing.model_validate(
        {"routing_policies": {"example": {"statements": [{"action": "accept", "conditions": []}]}}}
    )

    assert routing.model_dump()["routing_policies"]["example"]["statements"][0]["set_attributes"] == []


@pytest.mark.parametrize(
    "attributes",
    [
        "not a list",
        [{"set_type": 123, "set_target": "200"}],
        [{"set_type": "metric", "set_target": 50}],
        [{"set_type": "metric"}],
        [{"set_target": "50"}],
    ],
)
def test_routing_policy_invalid_set_attributes(attributes):
    with pytest.raises(ValidationError):
        f_routing.model_validate(
            {
                "routing_policies": {
                    "example": {"statements": [{"action": "accept", "conditions": [], "set_attributes": attributes}]}
                }
            }
        )

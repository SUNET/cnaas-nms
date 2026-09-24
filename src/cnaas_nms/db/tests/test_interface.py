import unittest

from pydantic import ValidationError

from cnaas_nms.db.interface import Interface
from cnaas_nms.db.settings import check_interface_tagged_vlan_groups
from cnaas_nms.db.settings_fields import f_interface


class InterfaceTests(unittest.TestCase):
    def test_interface_index_num(self):
        self.assertEqual(Interface.interface_index_num("Ethernet1"), 2)
        self.assertEqual(Interface.interface_index_num("GigabitEthernet1/0"), 201)
        self.assertEqual(Interface.interface_index_num("Eth98/98/98"), 999999)
        self.assertEqual(Interface.interface_index_num("xe-4/3/2/1"), 5040302)
        with self.assertRaises(ValueError):
            Interface.interface_index_num("Ethernet")

    def test_interface_tagged_vlan_list_group(self):
        # Test that setting both tagged_vlan_list and tagged_vlan_groups raises a ValidationError
        with self.assertRaises(ValidationError) as context:
            f_interface(
                name="Ethernet1",
                ifclass="port_template_tagged",
                tagged_vlan_list=[1, 2, 3],
                tagged_vlan_groups=["group1"],
            )

        self.assertIn("tagged_vlan_list and tagged_vlan_groups cannot be set at the same time", str(context.exception))

    def test_interface_tagged_vlan(self):
        f_interface(name="Ethernet1", ifclass="port_template_tagged", tagged_vlan_list=[1, 2, 3])
        f_interface(name="Ethernet1", ifclass="port_template_tagged", tagged_vlan_groups=["group1"])

    def test_interface_tagged_vlan_groups_check(self):
        # Test that check_interface_tagged_vlan_groups raises an error for undefined VLAN groups
        settings_dict = {"interfaces": [{"name": "Ethernet1", "tagged_vlan_groups": ["group1"]}], "vlan_groups": []}
        with self.assertRaises(Exception) as context:
            check_interface_tagged_vlan_groups(settings_dict)
        self.assertIn(
            "VLAN group 'group1' for interface 'Ethernet1' is not defined in vlan_groups", str(context.exception)
        )


if __name__ == "__main__":
    unittest.main()

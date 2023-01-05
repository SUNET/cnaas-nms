import unittest

from cnaas_nms.db.interface import Interface


class InterfaceTests(unittest.TestCase):
    def test_interface_index_num(self):
        self.assertEqual(Interface.interface_index_num("Ethernet1"), 2)
        self.assertEqual(Interface.interface_index_num("GigabitEthernet1/0"), 201)
        self.assertEqual(Interface.interface_index_num("Eth98/98/98"), 999999)
        self.assertEqual(Interface.interface_index_num("xe-4/3/2/1"), 5040302)
        with self.assertRaises(ValueError):
            Interface.interface_index_num("Ethernet")


if __name__ == "__main__":
    unittest.main()

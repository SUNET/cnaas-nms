import ipaddress
import unittest

from cnaas_nms.tools.jinja_filters import increment_ip, isofy_ipv4, ipv4_to_ipv6, get_interface


class JinjaFilterTests(unittest.TestCase):
    def test_increment_ipv4_plain(self):
        self.assertEqual(increment_ip("10.0.0.1"), "10.0.0.2")
        self.assertEqual(increment_ip(increment_ip("10.0.0.1")), "10.0.0.3")
        self.assertEqual(increment_ip("10.0.0.3", 4), "10.0.0.7")
        self.assertEqual(increment_ip("10.0.0.1", 255), "10.0.1.0")
        self.assertEqual(increment_ip("10.0.0.2", -1), "10.0.0.1")

    def test_increment_ipv4_prefix(self):
        self.assertEqual(increment_ip("10.0.0.1/24"), "10.0.0.2/24")
        self.assertNotEqual(increment_ip("10.0.0.1/24", 1), "10.0.0.2/32")
        self.assertEqual(increment_ip(increment_ip("10.0.0.1/24")), "10.0.0.3/24")
        self.assertEqual(increment_ip("10.0.0.3/24", 4), "10.0.0.7/24")
        with self.assertRaises(ValueError):
            increment_ip("10.0.0.1/24", 255)
        self.assertEqual(increment_ip("10.0.0.2/24", -1), "10.0.0.1/24")
        self.assertEqual(increment_ip("10.0.0.1/16", 255), "10.0.1.0/16")

    def test_increment_ipv6_plain(self):
        self.assertEqual(increment_ip("2001:700:3901:0020::1"), "2001:700:3901:20::2")
        self.assertEqual(increment_ip("2001:700:3901:0020::9"), "2001:700:3901:20::a")
        self.assertEqual(increment_ip("2001:700:3901:0020::1", -2), "2001:700:3901:1f:ffff:ffff:ffff:ffff")

    def test_increment_ipv6_prefix(self):
        self.assertEqual(increment_ip("2001:700:3901:0020::1/64"), "2001:700:3901:20::2/64")
        self.assertEqual(increment_ip("2001:700:3901:0020::9/64"), "2001:700:3901:20::a/64")
        with self.assertRaises(ValueError):
            increment_ip("2001:700:3901:0020::1/64", -2)

    def test_isofy_ipv4(self):
        self.assertEqual(isofy_ipv4("10.255.255.1"), "0102.5525.5001.00")
        self.assertEqual(isofy_ipv4("130.242.1.28"), "1302.4200.1028.00")
        self.assertEqual(isofy_ipv4("10.0.0.1"), "0100.0000.0001.00")
        with self.assertRaises(ValueError):
            isofy_ipv4("10.256.255.1")

    def test_isofy_ipv4_prefix(self):
        self.assertEqual(
            isofy_ipv4("130.242.1.28", prefix="47.0023.0000.0001.0000"),
            "47.0023.0000.0001.0000.1302.4200.1028.00",
        )
        self.assertEqual(
            isofy_ipv4("130.242.1.28", prefix="47.0023.0000.0001"),
            "47.0023.0000.0001.1302.4200.1028.00",
        )
        self.assertEqual(isofy_ipv4("130.242.1.28", "47"), "47.1302.4200.1028.00")
        invalid_prefixes = [
            "47.0023.0000.0001.00",
            "47.0023.0000.0001.000",
            "47.0023.0000.0001.0000.",
            "0047.0023.0000.0001.0000",
        ]
        for prefix in invalid_prefixes:
            with self.assertRaises(ValueError):
                isofy_ipv4("10.0.0.1", prefix=prefix)


class IPv6ToIPv4Tests(unittest.TestCase):
    """Test for the ipv4_to_ipv6 filter function."""

    def test_should_convert_short_network_properly(self):
        self.assertEqual(
            ipv4_to_ipv6("2001:700::/64", "10.0.0.1"),
            ipaddress.IPv6Interface("2001:700::10.0.0.1/64"),
        )

    def test_should_convert_long_network_properly(self):
        self.assertEqual(
            ipv4_to_ipv6("2001:700:dead:c0de:babe::/80", "10.0.0.1"),
            ipaddress.IPv6Interface("2001:700:dead:c0de:babe::10.0.0.1/80"),
        )

    def test_should_raise_on_invalid_network(self):
        with self.assertRaises(ValueError):
            invalid_network = "2001:700:0:::/64"
            ipv4_to_ipv6(invalid_network, "10.0.0.1")

    def test_should_return_an_ipv6interface(self):
        result = ipv4_to_ipv6("2001:700::/64", "10.0.0.1")
        self.assertIsInstance(result, ipaddress.IPv6Interface)


class GetInterfaceTests(unittest.TestCase):
    """Test for the get_interface filter function."""

    def test_should_return_correct_ipv4_interface(self):
        self.assertEqual(get_interface("10.0.1.0/24", 2), ipaddress.IPv4Interface("10.0.1.2/24"))

    def test_should_return_correct_ipv6_interface(self):
        self.assertEqual(
            get_interface("2001:700:dead:c0de::/64", 2),
            ipaddress.IPv6Interface("2001:700:dead:c0de::2/64"),
        )

    def test_should_raise_on_invalid_network(self):
        with self.assertRaises(ValueError):
            invalid_network = "2001:700:0:::/64"
            get_interface(invalid_network, 2)


if __name__ == "__main__":
    unittest.main()

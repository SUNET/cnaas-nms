import ipaddress
import unittest

from cnaas_nms.tools.jinja_filters import (
    increment_ip,
    isofy_ipv4,
    ipv4_to_ipv6,
    get_interface,
    ipwrap,
    b16encode,
    b16decode,
    b64encode,
    b64decode,
    sha1,
    sha256,
    sha512,
    md5,
)


class JinjaFilterTests(unittest.TestCase):
    def test_increment_ipv4_plain(self):
        self.assertEqual(increment_ip('10.0.0.1'), '10.0.0.2')
        self.assertEqual(increment_ip(increment_ip('10.0.0.1')), '10.0.0.3')
        self.assertEqual(increment_ip('10.0.0.3', 4), '10.0.0.7')
        self.assertEqual(increment_ip('10.0.0.1', 255), '10.0.1.0')
        self.assertEqual(increment_ip('10.0.0.2', -1), '10.0.0.1')

    def test_increment_ipv4_prefix(self):
        self.assertEqual(increment_ip('10.0.0.1/24'), '10.0.0.2/24')
        self.assertNotEqual(increment_ip('10.0.0.1/24', 1), '10.0.0.2/32')
        self.assertEqual(increment_ip(increment_ip('10.0.0.1/24')), '10.0.0.3/24')
        self.assertEqual(increment_ip('10.0.0.3/24', 4), '10.0.0.7/24')
        with self.assertRaises(ValueError):
            increment_ip('10.0.0.1/24', 255)
        self.assertEqual(increment_ip('10.0.0.2/24', -1), '10.0.0.1/24')
        self.assertEqual(increment_ip('10.0.0.1/16', 255), '10.0.1.0/16')

    def test_increment_ipv6_plain(self):
        self.assertEqual(increment_ip('2001:700:3901:0020::1'), '2001:700:3901:20::2')
        self.assertEqual(increment_ip('2001:700:3901:0020::9'), '2001:700:3901:20::a')
        self.assertEqual(
            increment_ip('2001:700:3901:0020::1', -2), '2001:700:3901:1f:ffff:ffff:ffff:ffff'
        )

    def test_increment_ipv6_prefix(self):
        self.assertEqual(increment_ip('2001:700:3901:0020::1/64'), '2001:700:3901:20::2/64')
        self.assertEqual(increment_ip('2001:700:3901:0020::9/64'), '2001:700:3901:20::a/64')
        with self.assertRaises(ValueError):
            increment_ip('2001:700:3901:0020::1/64', -2)

    def test_isofy_ipv4(self):
        self.assertEqual(isofy_ipv4('10.255.255.1'), '0102.5525.5001.00')
        self.assertEqual(isofy_ipv4('130.242.1.28'), '1302.4200.1028.00')
        self.assertEqual(isofy_ipv4('10.0.0.1'), '0100.0000.0001.00')
        with self.assertRaises(ValueError):
            isofy_ipv4('10.256.255.1')

    def test_isofy_ipv4_prefix(self):
        self.assertEqual(
            isofy_ipv4('130.242.1.28', prefix='47.0023.0000.0001.0000'),
            '47.0023.0000.0001.0000.1302.4200.1028.00',
        )
        self.assertEqual(
            isofy_ipv4('130.242.1.28', prefix='47.0023.0000.0001'),
            '47.0023.0000.0001.1302.4200.1028.00',
        )
        self.assertEqual(isofy_ipv4('130.242.1.28', '47'), '47.1302.4200.1028.00')
        invalid_prefixes = [
            '47.0023.0000.0001.00',
            '47.0023.0000.0001.000',
            '47.0023.0000.0001.0000.',
            '0047.0023.0000.0001.0000',
        ]
        for prefix in invalid_prefixes:
            with self.assertRaises(ValueError):
                isofy_ipv4('10.0.0.1', prefix=prefix)


class IPWrapTests(unittest.TestCase):
    """Tests for the ipwrap filter function"""

    def test_should_wrap_ipv6_string_in_brackets(self):
        address = "fe80:c0ff:eeba:be::"
        self.assertEqual(ipwrap(address), f"[{address}]")

    def test_should_wrap_ipv6_address_object_in_brackets(self):
        address = ipaddress.IPv6Address("fe80:c0ff:eeba:be::")
        self.assertEqual(ipwrap(address), f"[{address}]")

    def test_should_not_wrap_ipv4_address(self):
        address = "10.0.1.42"
        self.assertEqual(ipwrap(address), address)

    def test_should_not_wrap_fqdn(self):
        address = "wwww.example.org"
        self.assertEqual(ipwrap(address), address)

    def test_should_not_wrap_ints(self):
        address = 338288761799928348595999619069446717440
        self.assertEqual(ipwrap(address), str(address))


class IPv6ToIPv4Tests(unittest.TestCase):
    """Tests for the ipv4_to_ipv6 filter function"""

    def test_should_convert_short_network_properly(self):
        self.assertEqual(
            ipv4_to_ipv6('10.0.0.1', '2001:700::/64'),
            ipaddress.IPv6Interface('2001:700::1/64'),
        )

    def test_should_convert_long_network_properly(self):
        self.assertEqual(
            ipv4_to_ipv6('10.0.0.1', '2001:700:dead:c0de::/64', keep_octets=4),
            ipaddress.IPv6Interface('2001:700:dead:c0de:10:0:0:1/64'),
        )

    def test_should_raise_on_invalid_network(self):
        with self.assertRaises(ValueError):
            invalid_network = '2001:700:0:::/64'
            ipv4_to_ipv6('10.0.0.1', invalid_network)

    def test_should_return_an_ipv6interface(self):
        result = ipv4_to_ipv6('10.0.0.1', '2001:700::/64')
        self.assertIsInstance(result, ipaddress.IPv6Interface)


class GetInterfaceTests(unittest.TestCase):
    """Tests for the get_interface filter function"""

    def test_should_return_correct_ipv4_interface(self):
        self.assertEqual(get_interface('10.0.1.0/24', 2), ipaddress.IPv4Interface('10.0.1.2/24'))

    def test_should_return_correct_ipv6_interface(self):
        self.assertEqual(
            get_interface('2001:700:dead:c0de::/64', 2),
            ipaddress.IPv6Interface('2001:700:dead:c0de::2/64'),
        )

    def test_should_raise_on_invalid_network(self):
        with self.assertRaises(ValueError):
            invalid_network = '2001:700:0:::/64'
            get_interface(invalid_network, 2)


class BaseCodingTests(unittest.TestCase):
    def test_b64(self):
        teststr = "aB1_/ö# [;"
        self.assertEqual(
            teststr,
            b64decode(b64encode(teststr))
        )

    def test_b16(self):
        teststr = "aB1_/ö# [;"
        self.assertEqual(
            teststr,
            b16decode(b16encode(teststr))
        )


class HashTests(unittest.TestCase):
    def test_sha1(self):
        self.assertEqual(
            sha1("M7urErP1V7Pi6S+PjR3/mQ6iXAs="),
            "5196ef4746d7ea377114f2f052c74a1533621ec3",
        )

    def test_sha256(self):
        self.assertEqual(
            sha256("zaoW4e3+2R2nAt5uXolY0pwiU/CjpriaY6EOvi26UoY="),
            "3525c9b29e65cc46645c755bb91c3bfbb36c6f122b8e33845b4e3e728854dba9",
        )

    def test_sha512(self):
        self.assertEqual(
            sha512("Zij3NjTWHt9W4Ljuez7QpJTo5O/Fg+z8bKzWMev+n3lXcEhTv9dnL1Zs"
                   "fJBocAR19QBjLz747LhqkDiQBOuOuw=="),
            "6f7affc55e52d24b6da48182ceae1007a3f7fcdee6ad7e3eae0858e02d98786"
            "cc04e9a329126d31cdf427214ea07428dd61e67b56b9f568e221c4553f391d02e",
        )

    def test_md5(self):
        self.assertEqual(
            md5("zKEPXmRX2X9itoaaI2kWyQ=="),
            "88a23549d423a601c96b4bf90018bde6",
        )


if __name__ == '__main__':
    unittest.main()

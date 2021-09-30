import unittest

from cnaas_nms.tools.jinja_filters import increment_ip, isofy_ipv4, ipv4_to_ipv6


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

    def test_ipv4_to_ipv6(self):
        self.assertEqual(ipv4_to_ipv6('2001:700::/64', '10.0.0.1'), '2001:700::10:0:0:1/64')
        self.assertEqual(ipv4_to_ipv6('2001:700:0::/64', '10.0.0.1'), '2001:700::10:0:0:1/64')
        with self.assertRaises(ValueError):
            invalid_network = '2001:700:0:::/64'
            ipv4_to_ipv6(invalid_network, '10.0.0.1')

    def test_ipv4to6_prefix(self):
        self.assertNotEqual(ipv4_to_ipv6('2001:700::/64', '10.0.0.1'), '2001:700::10:0:0:1')

    def test_ipv4to6_compressed_notation(self):
        self.assertNotEqual(ipv4_to_ipv6('2001:700:0::/64', '10.0.0.1'), '2001:700:0::10:0:0:1/64')
        self.assertNotEqual(
            ipv4_to_ipv6('2001:0700:0000::/64', '10.0.0.1'), '2001:0700:0000::10:0:0:1/64'
        )
        self.assertNotEqual(ipv4_to_ipv6('2001:700::/64', '10.00.0.1'), '2001:700::10:00:0:1/64')


if __name__ == '__main__':
    unittest.main()

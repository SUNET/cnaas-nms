import unittest

from cnaas_nms.tools.jinja_filters import increment_ip


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


if __name__ == '__main__':
    unittest.main()

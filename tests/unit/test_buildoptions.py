#pylint: skip-file

import unittest
from rdgo import utils

try:
    from unittest.mock import ANY, patch, call
except ImportError:
    try:
        from mock import ANY, patch, call
    except ImportError:
        # Mock is already set to False
        raise ImportError("You need to have unittest or mock python module to run the unittest")

class TestRpmBuildOptions(unittest.TestCase):
    """
    Unit tests for added build options related functions
    """

    def test_key_value_pair_conversion(self):
        key_value_pairs = {"foo" : "bar",
                           "baz" : "blar"}

        output = utils.convert_key_pair_into_commands(key_value_pairs)
        self.assertEqual(output, '--define "foo bar" --define "baz blar"')

        # We don't allow numbers as input atm
        key_num_pairs = {"foo" : 0, "baz" : 1}
        self.assertRaises(TypeError, utils.convert_key_pair_into_commands, key_num_pairs)

        # When key is a number based, error out
        num_value_pairs ={ 0 : "1"}
        self.assertRaises(TypeError, utils.convert_key_pair_into_commands, num_value_pairs)

if __name__ == '__main__':
    unittest.main()

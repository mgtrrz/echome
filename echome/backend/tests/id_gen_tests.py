import unittest
from ../id_gen import id_gen

class NamesTestCase(unittest.TestCase):

   def test_first_last_name(self):
       result = formatted_name("pete", "seeger")
       self.assertEqual(result, "Pete Seeger")
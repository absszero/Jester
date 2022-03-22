from sublime import find_resources

from . import unittest
from Jester.plugin import find_test_name_in_selection


class TestFindSelectedTestName(unittest.ViewTestCase):

    def test_empty(self):
        self.fixture('')
        self.assertEqual(None, find_test_name_in_selection(self.view))

    def test_none_when_plain_text(self):
        self.fixture('foo|bar')
        self.assertEqual(None, find_test_name_in_selection(self.view))

    def test_test_function(self):
        self.fixture("""test('aaaa', () => {
                expect(1 + 1).toBe(2);|
            });
        """)

        self.assertEqual("aaaa", find_test_name_in_selection(self.view))

    def test_it_function(self):
        self.fixture("""it('aaaa', () => {
                expect(1 + 1).toBe(2);|
            });
        """)

        self.assertEqual("aaaa", find_test_name_in_selection(self.view))

    def test_describe_function(self):
        self.fixture("""describe('yourModule', () => {|
              test('cccc', () => {});
            });
        """)

        self.assertEqual("yourModule", find_test_name_in_selection(self.view))

    def test_test_function_in_describe(self):
        self.fixture("""describe('yourModule', () => {
              test('cccc', () => {|});
            });
        """)

        self.assertEqual("cccc", find_test_name_in_selection(self.view))

    def test_it_function_in_describe(self):
        self.fixture("""describe('yourModule', () => {
              it('cccc', () => {|});
            });
        """)

        self.assertEqual("cccc", find_test_name_in_selection(self.view))

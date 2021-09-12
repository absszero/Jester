from sublime import find_resources
import importlib

from . import unittest
plugin = importlib.import_module("sublime-jester.plugin")


class TestFindSelectedTestName(unittest.ViewTestCase):

    def test_empty(self):
        self.fixture('')
        self.assertEqual(None, plugin.find_test_name_in_selection(self.view))

    def test_none_when_plain_text(self):
        self.fixture('foo|bar')
        self.assertEqual(None, plugin.find_test_name_in_selection(self.view))

    def test_test_function(self):
        self.fixture("""test('aaaa', () => {
                expect(1 + 1).toBe(2);|
            });
        """)

        self.assertEqual("aaaa", plugin.find_test_name_in_selection(self.view))

    def test_it_function(self):
        self.fixture("""it('aaaa', () => {
                expect(1 + 1).toBe(2);|
            });
        """)

        self.assertEqual("aaaa", plugin.find_test_name_in_selection(self.view))

    def test_describe_function(self):
        self.fixture("""describe('yourModule', () => {|
              test('cccc', () => {});
            });
        """)

        self.assertEqual("yourModule", plugin.find_test_name_in_selection(self.view))

    def test_test_function_in_describe(self):
        self.fixture("""describe('yourModule', () => {
              test('cccc', () => {|});
            });
        """)

        self.assertEqual("cccc", plugin.find_test_name_in_selection(self.view))

    def test_it_function_in_describe(self):
        self.fixture("""describe('yourModule', () => {
              it('cccc', () => {|});
            });
        """)

        self.assertEqual("cccc", plugin.find_test_name_in_selection(self.view))

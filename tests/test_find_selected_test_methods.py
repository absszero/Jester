from . import unittest
from Jester.plugin import escape_test_name_for_jest
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

    def test_modified_test_functions(self):
        fixtures = [
            ("test.only('only test', () => {|});", 'only test'),
            ("it.skip('skipped test', () => {|});", 'skipped test'),
            ("test.todo('todo test|');", 'todo test'),
            ("test.each([[1, 1]])('each %i', (a, b) => {|});", 'each %i'),
        ]

        for source, expected in fixtures:
            with self.subTest(source=source):
                self.fixture(source)
                self.assertEqual(expected, find_test_name_in_selection(self.view))

    def test_escape_test_names_for_jest(self):
        self.assertEqual(
            r'adds \(1\+1\)',
            escape_test_name_for_jest('adds (1+1)')
        )
        self.assertEqual(
            r'adds .*',
            escape_test_name_for_jest('adds %i', is_each=True)
        )
        self.assertEqual(
            'cost 100%',
            escape_test_name_for_jest('cost 100%%', is_each=True)
        )

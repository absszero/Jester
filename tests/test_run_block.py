from . import unittest
from Jester.plugin import Jester


class TestJesterRunBlock(unittest.TestCase):

    def test_no_test_at_cursor_does_not_run_file(self):
        jester = Jester.__new__(Jester)
        jester.view = unittest.mock.Mock()
        jester.view.file_name.return_value = 'example.spec.js'
        jester.view.sel.return_value = [unittest.mock.Mock()]
        jester.view.find_by_selector.return_value = []
        jester.run = unittest.mock.Mock()

        with unittest.mock.patch('Jester.plugin.status_message') as status_message:
            jester.run_block({})

        status_message.assert_called_once_with('Jester: no test found at cursor')
        jester.run.assert_not_called()

    def test_run_block_escapes_test_name(self):
        jester = Jester.__new__(Jester)
        jester.view = unittest.mock.Mock()
        jester.view.file_name.return_value = 'example.spec.js'
        jester.run = unittest.mock.Mock()

        with unittest.mock.patch(
            'Jester.plugin.find_test_call_in_selection',
            return_value=('adds (1+1)', False)
        ):
            jester.run_block({})

        jester.run.assert_called_once_with(
            file='example.spec.js',
            options={'t': r'adds \(1\+1\)'}
        )
import os
import shutil
import sublime
import sublime_plugin

from sublime import active_window
from sublime import platform
from sublime import status_message
from re import compile

settings = None


def get_settings(key: str, default=None):
    global settings

    if settings is None:
        settings = sublime.load_settings('Jester.sublime-settings')

    return settings.get(key, default)


def debug_message(msg, *args):
    if not get_settings('debug'):
        return

    if args:
        msg = msg % argson_post_save
    print('Jester: ' + msg)


def message(msg, *args):
    if args:
        msg = msg % args

    msg = 'Jester: ' + msg

    print(msg)
    status_message(msg)


def get_window_setting(key, default=None, window=None):
    if not window:
        window = active_window()

    if window.settings().has(key):
        return window.settings().get(key)

    view = window.active_view()

    if view and view.settings().has(key):
        return view.settings().get(key)

    return default


def set_window_setting(key, value, window):
    window.settings().set(key, value)


def find_jest_configuration_file(file_name, folders):
    """
    Find the first Jest configuration file.

    Jest's configuration can be defined in the package.json file of your project,
    or through a jest.config.js, or jest.config.ts, we only search the last two files.
    """
    debug_message('find configuration for \'%s\' ...', file_name)
    debug_message('  found %d folders %s', len(folders) if folders else 0, folders)

    if file_name is None:
        return None

    if not isinstance(file_name, str):
        return None

    if not len(file_name) > 0:
        return None

    if folders is None:
        return None

    if not isinstance(folders, list):
        return None

    if not len(folders) > 0:
        return None

    ancestor_folders = []  # type: list
    common_prefix = os.path.commonprefix(folders)
    parent = os.path.dirname(file_name)
    while parent not in ancestor_folders and parent.startswith(common_prefix):
        ancestor_folders.append(parent)
        parent = os.path.dirname(parent)

    ancestor_folders.sort(reverse=True)

    debug_message('  found %d possible locations %s', len(ancestor_folders), ancestor_folders)

    candidate_configuration_file_names = ['jest.config.js', 'jest.config.ts']
    debug_message('  looking for %s ...', candidate_configuration_file_names)
    for folder in ancestor_folders:
        for file_name in candidate_configuration_file_names:
            configuration_file = os.path.join(folder, file_name)
            if os.path.isfile(configuration_file):
                debug_message('  found configuration \'%s\'', configuration_file)
                return configuration_file

    debug_message('  no configuration found')

    return None


def find_working_directory(file_name, folders):
    configuration_file = find_jest_configuration_file(file_name, folders)
    if configuration_file:
        return os.path.dirname(configuration_file)


def find_test_name_in_selection(view):
    """
    Return a list of selected test method names.

    Return an empty list if no selections found.

    Selection can be anywhere inside one or more test methods.
    """

    def find_test_name(view, region, selected):
        if not region.contains(selected):
            return None

        pattern = compile(r"^(describe|test|it)\s*\((['\"])([^'\"]*)\2")
        matched = pattern.search(view.substr(region))
        test_name = matched and matched.group(3)
        return test_name

    selected = view.sel()[0]
    function_regions = view.find_by_selector('meta.function-call meta.function-call')
    for function_region in function_regions:
        test_name = find_test_name(view, function_region, selected)
        if test_name:
            return test_name

    function_regions = view.find_by_selector('meta.function-call')
    selected = view.sel()[0]
    for function_region in function_regions:
        test_name = find_test_name(view, function_region, selected)
        if test_name:
            return test_name


def exec_file_regex():
    if platform() == 'windows':
        return '((?:[a-zA-Z]\\:)?\\\\[a-zA-Z0-9 \\.\\/\\\\_-]+)(?: on line |\\:)([0-9]+)'
    else:
        return '(\\/[a-zA-Z0-9 \\.\\/_-]+)(?: on line |\\:)([0-9]+)'


def is_file_executable(file):
    if file is None:
        return False
    return os.path.isfile(file) and os.access(file, os.X_OK)


def build_cmd_options(options, cmd):
    for k, v in options.items():
        if v:
            if len(k) == 1:
                if isinstance(v, list):
                    for _v in v:
                        cmd.append('-' + k)
                        cmd.append(_v)
                else:
                    cmd.append('-' + k)
                    if v is not True:
                        cmd.append(v)
            else:
                if k[-1] == '=':
                    cmd.append('--' + k + v)
                else:
                    cmd.append('--' + k)
                    if v is not True:
                        cmd.append(v)

    return cmd


def filter_path(path):
    return os.path.expandvars(os.path.expanduser(path))


def _get_jest_executable(working_dir):
    locations = [
        os.path.join(working_dir, os.path.join('node_modules', '.bin', 'jest.cmd')),
        os.path.join(working_dir, os.path.join('node_modules', '.bin', 'jest')),
        shutil.which('jest')
    ]
    for location in locations:
        debug_message('  found jest_location:\'%s\'', location)
        if is_file_executable(location):
            debug_message('  found jest_executable:\'%s\'', location)
            return location

    raise ValueError('jest not executable')


class Jester():

    def __init__(self, window):
        self.window = window
        self.view = self.window.active_view()
        if not self.view:
            raise ValueError('view not found')

        debug_message('init %s', self.view.file_name())

    def run(self, working_dir=None, file=None, options=None):
        debug_message('run working_dir=%s, file=%s, options=%s', working_dir, file, options)

        # Kill any currently running tests
        self.window.run_command('exec', {'kill': True})

        env = {}
        cmd = []

        try:
            if not working_dir:
                working_dir = find_working_directory(self.view.file_name(), self.window.folders())
                if not working_dir:
                    raise ValueError('working directory not found')

            if not os.path.isdir(working_dir):
                raise ValueError('working directory does not exist or is not a valid directory')

            debug_message('working dir \'%s\'', working_dir)

            jest_executable = self.get_jest_executable(working_dir)
            cmd.append(jest_executable)

            options = self.filter_options(options)
            debug_message('options %s', options)

            cmd = build_cmd_options(options, cmd)
            if file:
                if os.path.isfile(file):
                    cmd.append(file)
                else:
                    raise ValueError('test file \'%s\' not found' % file)

        except ValueError as e:
            status_message('Jester: {}'.format(e))
            print('Jester: {}'.format(e))
            return
        except Exception as e:
            status_message('Jester: {}'.format(e))
            print('Jester: \'{}\''.format(e))
            raise e

        debug_message('env %s', env)
        debug_message('cmd %s', cmd)

        set_window_setting('Jester._test_last', {
            'working_dir': working_dir,
            'file': file,
            'options': options
        }, window=self.window)

        self.window.run_command('exec', {
            'env': env,
            'cmd': cmd,
            'file_regex': exec_file_regex(),
            'quiet': not get_settings('debug'),
            'shell': False,
            'syntax': 'Packages/{}/res/text-ui-result.sublime-syntax'.format(__name__.split('.')[0]),
            'word_wrap': False,
            'working_dir': working_dir
        })

        panel = self.window.create_output_panel('exec')

        header_text = []
        if env:
            header_text.append("env: {}\n".format(env))

        header_text.append("{}\n\n".format(' '.join(cmd)))

        panel.run_command('insert', {'characters': ''.join(header_text)})

        panel_settings = panel.settings()
        panel_settings.set('rulers', [])

        if self.view.settings().has('Jester.text_ui_result_font_size'):
            panel_settings.set(
                'font_size',
                self.view.settings().get('Jester.text_ui_result_font_size')
            )

    def run_last(self):
        last_test_args = get_window_setting('Jester._test_last', window=self.window)
        if not last_test_args:
            return status_message('Jester: no tests were run so far')

        self.run(**last_test_args)

    def run_file(self, options=None):
        if options is None:
            options = {}

        file = self.view.file_name()
        if not self.is_test_file(file):
            return status_message('Jester: not a test file')

        self.run(file=file, options=options)

    def is_test_file(self, file):
        return bool(file and (
                file.endswith('.js') or
                file.endswith('.ts') or
                file.endswith('.jsx')
            )
        )

    def run_block(self, options):
        file = self.view.file_name()
        if not self.is_test_file(file):
            return status_message('Jester: not a test file')

        test_name = find_test_name_in_selection(self.view)
        if test_name:
            options['t'] = test_name

        self.run(file=file, options=options)

    def filter_options(self, options):
        if options is None:
            options = {}

        window_options = get_window_setting('jester.options', default={}, window=self.window)
        debug_message('window options %s', window_options)
        if window_options:
            for k, v in window_options.items():
                if k not in options:
                    options[k] = v

        view_options = self.view.settings().get('jester.options')
        debug_message('view options %s', view_options)
        if view_options:
            for k, v in view_options.items():
                if k not in options:
                    options[k] = v

        return options

    def get_jest_executable(self, working_dir):
        executable = get_settings('jest_execution')
        if executable:
            executable = filter_path(executable)
            debug_message('jester.jest_execution = %s', executable)
            return executable

        return _get_jest_executable(working_dir)


class JesterTestSuiteCommand(sublime_plugin.WindowCommand):

    def run(self, **kwargs):
        Jester(self.window).run(options=kwargs)


class JesterTestFileCommand(sublime_plugin.WindowCommand):

    def run(self, **kwargs):
        Jester(self.window).run_file(options=kwargs)


class JesterTestLastCommand(sublime_plugin.WindowCommand):

    def run(self):
        Jester(self.window).run_last()


class JesterTestBlockCommand(sublime_plugin.WindowCommand):

    def run(self, **kwargs):
        Jester(self.window).run_block(options=kwargs)

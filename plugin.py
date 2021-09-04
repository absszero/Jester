import re
import os
import shutil
import sublime_plugin

from sublime import ENCODED_POSITION
from sublime import active_window
from sublime import cache_path
from sublime import platform
from sublime import status_message
from sublime import load_resource
from re import compile


_DEBUG = bool(os.getenv('SUBLIME_JESTER_DEBUG'))

if _DEBUG:
    def debug_message(msg, *args):
        if args:
            msg = msg % args
        print('Jester: ' + msg)
else:  # pragma: no cover
    def debug_message(msg, *args):
        pass


def message(msg, *args):
    if args:
        msg = msg % args

    msg = 'Jester: ' + msg

    print(msg)
    status_message(msg)


def is_debug(view=None):
    if view:
        Jester_debug = view.settings().get('Jester.debug')
        return Jester_debug or (
            Jester_debug is not False and view.settings().get('debug')
        )
    else:
        return _DEBUG


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


def is_valid_php_identifier(string):
    return re.match('^[a-zA-Z_][a-zA-Z0-9_]*$', string)


def has_test_case(view):
    """Return True if the view contains a valid Jester test case."""
    for php_class in find_php_classes(view):
        if php_class[-4:] == 'Test':
            return True
    return False


def find_php_classes(view, with_namespace=False):
    """Return list of class names defined in the view."""
    classes = []

    namespace = None
    # for namespace_region in view.find_by_selector('entity.name.function'):
    for namespace_region in view.find_by_selector('meta.function-call'):
        namespace = view.substr(namespace_region)
        print(namespace)

    for class_as_region in view.find_by_selector('source.php entity.name.class - meta.use'):
        class_as_string = view.substr(class_as_region)
        if is_valid_php_identifier(class_as_string):
            if with_namespace:
                classes.append({
                    'namespace': namespace,
                    'class': class_as_string
                })
            else:
                classes.append(class_as_string)

    # BC: < 3114
    if not classes:  # pragma: no cover
        for class_as_region in view.find_by_selector('source.php entity.name.type.class - meta.use'):
            class_as_string = view.substr(class_as_region)
            if is_valid_php_identifier(class_as_string):
                classes.append(class_as_string)

    return classes


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


def get_color_scheme(color_scheme):
    """Try to patch color scheme with default test result colors."""

    if color_scheme.endswith('.sublime-color-scheme'):
        return color_scheme

    try:
        color_scheme_resource = load_resource(color_scheme)
        if 'Jester' in color_scheme_resource or 'Jester' in color_scheme_resource:
            return color_scheme

        if 'region.greenish' in color_scheme_resource:
            return color_scheme

        cs_head, cs_tail = os.path.split(color_scheme)
        cs_package = os.path.split(cs_head)[1]
        cs_name = os.path.splitext(cs_tail)[0]

        file_name = cs_package + '__' + cs_name + '.hidden-tmTheme'
        abs_file = os.path.join(cache_path(), __name__.split('.')[0], 'color-schemes', file_name)
        rel_file = 'Cache/{}/color-schemes/{}'.format(__name__.split('.')[0], file_name)

        debug_message('auto generating color scheme = %s', rel_file)

        if not os.path.exists(os.path.dirname(abs_file)):
            os.makedirs(os.path.dirname(abs_file))

        color_scheme_resource_partial = load_resource(
            'Packages/{}/res/text-ui-result-theme-partial.txt'.format(__name__.split('.')[0]))

        with open(abs_file, 'w', encoding='utf8') as f:
            f.write(re.sub(
                '</array>\\s*'
                '((<!--\\s*)?<key>.*</key>\\s*<string>[^<]*</string>\\s*(-->\\s*)?)*'
                '</dict>\\s*</plist>\\s*'
                '$',

                color_scheme_resource_partial + '\\n</array></dict></plist>',
                color_scheme_resource
            ))

        return rel_file
    except Exception as e:
        print('Jester: an error occurred trying to patch color'
              ' scheme with Jester test results colors: {}'.format(str(e)))

    return color_scheme


class Switchable:

    def __init__(self, location):
        self.location = location
        self.file = location[0]

    def file_encoded_position(self, view):
        window = view.window()

        file = self.location[0]
        row = self.location[2][0]
        col = self.location[2][1]

        # If the file we're switching to is already open,
        # then by default don't goto encoded position.
        for v in window.views():
            if v.file_name() == self.location[0]:
                row = None
                col = None

        # If cursor is on a symbol like a class method,
        # then try find the relating test method or vice-versa,
        # and use that as the encoded position to jump to.
        symbol = view.substr(view.word(view.sel()[0].b))
        if symbol:
            if symbol[:4] == 'test':
                symbol = symbol[4:]
                symbol = symbol[0].lower() + symbol[1:]
            else:
                symbol = 'test' + symbol[0].upper() + symbol[1:]

            locations = window.lookup_symbol_in_open_files(symbol)
            if locations:
                for location in locations:
                    if location[0] == self.location[0]:
                        row = location[2][0]
                        col = location[2][1]
                        break

        encoded_postion = ''
        if row:
            encoded_postion += ':' + str(row)
        if col:
            encoded_postion += ':' + str(col)

        return file + encoded_postion


def refine_switchable_locations(locations, file):
    debug_message('refine location')
    if not file:
        return locations, False

    debug_message('file=%s', file)
    debug_message('locations=%s', locations)

    files = []
    if file.endswith('Test.php'):
        file_is_test_case = True
        file = file.replace('Test.php', '.php')
        files.append(re.sub('(\\/)?[tT]ests\\/([uU]nit\\/)?', '/', file))
        files.append(re.sub('(\\/)?[tT]ests\\/', '/src/', file))
    else:
        file_is_test_case = False
        file = file.replace('.php', 'Test.php')
        files.append(file)
        files.append(re.sub('(\\/)?src\\/', '/', file))
        files.append(re.sub('(\\/)?src\\/', '/test/', file))

    debug_message('files=%s', files)

    if len(locations) > 1:
        common_prefix = os.path.commonprefix([l[0] for l in locations])
        if common_prefix != '/':
            files = [file.replace(common_prefix, '') for file in files]

    for location in locations:
        loc_file = location[0]
        if not file_is_test_case:
            loc_file = re.sub('\\/[tT]ests\\/([uU]nit\\/)?', '/', loc_file)

        for file in files:
            if loc_file.endswith(file):
                return [location], True

    return locations, False


def find_switchable(view, on_select=None):
    # Args:
    #   view (View)
    #   on_select (callable)
    #
    # Returns:
    #   void
    window = view.window()

    if on_select is None:
        raise ValueError('a callable is required')

    file = view.file_name()
    debug_message('file=%s', file)

    classes = find_php_classes(view, with_namespace=True)
    if len(classes) == 0:
        return message('could not find a test case or class under test for %s', file)

    debug_message('file contains %s class %s', len(classes), classes)

    locations = []  # type: list
    for _class in classes:
        class_name = _class['class']

        if class_name[-4:] == 'Test':
            symbol = class_name[:-4]
        else:
            symbol = class_name + 'Test'

        symbol_locations = window.symbol_locations(symbol)
        print(symbol_locations)
        locations += symbol_locations

    debug_message('class has %s location %s', len(locations), locations)

    return

    def unique_locations(locations):
        locs = []
        seen = set()  # type: set
        for location in locations:
            if location[0] not in seen:
                seen.add(location[0])
                locs.append(location)

        return locs

    locations = unique_locations(locations)

    if len(locations) == 0:
        if has_test_case(view):
            return message('could not find class under test for %s', file)
        else:
            return message('could not find test case for %s', file)

    def _on_select(index):
        if index == -1:
            return

        switchable = Switchable(locations[index])

        if on_select is not None:
            on_select(switchable)

    locations, is_exact = refine_switchable_locations(locations=locations, file=file)

    debug_message('is_exact=%s', is_exact)
    debug_message('locations(%s)=%s', len(locations), locations)

    if is_exact and len(locations) == 1:
        return
        return _on_select(0)

    window.show_quick_panel(['{}:{}'.format(l[1], l[2][0]) for l in locations], _on_select)


def put_views_side_by_side(view_a, view_b):
    if view_a == view_b:
        return

    window = view_a.window()

    if window.num_groups() == 1:
        window.run_command('set_layout', {
            "cols": [0.0, 0.5, 1.0],
            "rows": [0.0, 1.0],
            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]
        })

    view_a_index = window.get_view_index(view_a)
    view_b_index = window.get_view_index(view_b)

    if window.num_groups() <= 2 and view_a_index[0] == view_b_index[0]:

        if view_a_index[0] == 0:
            window.set_view_index(view_b, 1, 0)
        else:
            window.set_view_index(view_b, 0, 0)

        # Ensure focus is not lost from either view.
        window.focus_view(view_a)
        window.focus_view(view_b)


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

        if self.view.settings().get('Jester.save_all_on_run'):
            # Write out every buffer in active
            # window that has changes and is
            # a real file on disk.
            for view in self.window.views():
                if view.is_dirty() and view.file_name():
                    view.run_command('save')

        set_window_setting('Jester._test_last', {
            'working_dir': working_dir,
            'file': file,
            'options': options
        }, window=self.window)

        if self.view.settings().get('Jester.strategy') == 'iterm':
            osx_iterm_script = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'bin', 'osx_iterm')

            cmd = [osx_iterm_script] + cmd

            self.window.run_command('exec', {
                'env': env,
                'cmd': cmd,
                'quiet': not is_debug(self.view),
                'shell': False,
                'working_dir': working_dir
            })
        else:
            self.window.run_command('exec', {
                'env': env,
                'cmd': cmd,
                'file_regex': exec_file_regex(),
                'quiet': not is_debug(self.view),
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

            color_scheme = get_color_scheme(self.view.settings().get('color_scheme'))
            panel_settings.set('color_scheme', color_scheme)

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

    def run_single_test(self, options):
        file = self.view.file_name()
        if not self.is_test_file(file):
            return status_message('Jester: not a test file')

        test_name = find_test_name_in_selection(self.view)
        if test_name:
            options['t'] = test_name

        self.run(file=file, options=options)

    def show_results(self):
        self.window.run_command('show_panel', {'panel': 'output.exec'})

    def cancel(self):
        self.window.run_command('exec', {'kill': True})

    def open_coverage_report(self):
        working_dir = find_working_directory(self.view.file_name(), self.window.folders())
        if not working_dir:
            return status_message('Jester: could not find a Jester working directory')

        coverage_html_index_html_file = os.path.join(working_dir, 'build/coverage/index.html')
        if not os.path.exists(coverage_html_index_html_file):
            return status_message('Jester: could not find Jester HTML code coverage %s' % coverage_html_index_html_file)  # noqa: E501

        import webbrowser
        webbrowser.open_new_tab('file://' + coverage_html_index_html_file)

    def switch(self):
        def _on_switchable(switchable):
            self.window.open_file(switchable.file_encoded_position(self.view), ENCODED_POSITION)
            put_views_side_by_side(self.view, self.window.active_view())

        find_switchable(self.view, on_select=_on_switchable)

    def visit(self):
        test_last = get_window_setting('Jester._test_last', window=self.window)
        if test_last:
            if 'file' in test_last and 'working_dir' in test_last:
                if test_last['file']:
                    file = os.path.join(test_last['working_dir'], test_last['file'])
                    if os.path.isfile(file):
                        return self.window.open_file(file)

        return status_message('Jester: no tests were run so far')

    def toggle_option(self, option, value=None):
        options = get_window_setting('Jester.options', default={}, window=self.window)

        if value is None:
            options[option] = not bool(options[option]) if option in options else True
        else:
            if option in options and options[option] == value:
                del options[option]
            else:
                options[option] = value

        set_window_setting('Jester.options', options, window=self.window)

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
        executable = self.view.settings().get('jester.executable')
        if executable:
            executable = filter_path(executable)
            debug_message('jester.executable = %s', executable)
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


class JesterTestSingleTestCommand(sublime_plugin.WindowCommand):

    def run(self, **kwargs):
        Jester(self.window).run_single_test(options=kwargs)


class JesterTestResultsCommand(sublime_plugin.WindowCommand):

    def run(self):
        Jester(self.window).show_results()


class JesterTestCancelCommand(sublime_plugin.WindowCommand):

    def run(self):
        Jester(self.window).cancel()


class JesterTestVisitCommand(sublime_plugin.WindowCommand):

    def run(self):
        Jester(self.window).visit()


class JesterTestSwitchCommand(sublime_plugin.WindowCommand):

    def run(self):
        Jester(self.window).switch()


class JesterToggleOptionCommand(sublime_plugin.WindowCommand):

    def run(self, option, value=None):
        Jester(self.window).toggle_option(option, value)


class JesterTestCoverageCommand(sublime_plugin.WindowCommand):

    def run(self):
        Jester(self.window).open_coverage_report()


class JesterEvents(sublime_plugin.EventListener):

    def on_post_save(self, view):
        file_name = view.file_name()
        if not file_name:
            return

        if not file_name.endswith('.php'):
            return

        on_post_save_events = view.settings().get('Jester.on_post_save')

        if 'run_test_file' in on_post_save_events:
            Jester(view.window()).run_file()


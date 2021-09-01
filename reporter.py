import os

from sublime import load_resource
from Jester.plugin import debug_message


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

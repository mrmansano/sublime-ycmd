#!/usr/bin/env python3

'''
lib/util/fs.py
File-system utilities.
'''

import itertools
import json
import logging
import os

logger = logging.getLogger('sublime-ycmd.' + __name__)


def is_directory(path):
    '''
    Returns true if the supplied `path` refers to a valid directory, and
    false otherwise.
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)
    return os.path.exists(path) and os.path.isdir(path)


def is_file(path):
    '''
    Returns true if the supplied `path` refers to a valid plain file, and
    false otherwise.
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)
    return os.path.exists(path) and os.path.isfile(path)


def get_directory_name(path):
    '''
    Returns the directory name for the file at `path`. If `path` refers to
    a directory, the parent directory is returned.
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)
    head, tail = os.path.split(path)
    if not tail and head != path:
        # stripped a trailing directory separator, so redo it
        head, tail = os.path.split(head)

    return head


def get_base_name(path):
    '''
    Returns the base name for the file at `path`. If `path` refers to a
    directory, the directory name is returned. If `path` refers to a mount
    point, the base name will be `None`.
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)
    head, tail = os.path.split(path)
    if tail:
        return tail
    if head != path:
        # stripped a trailing directory separator, so redo it
        head, tail = os.path.split(head)

    return tail


def load_json_file(path, encoding='utf-8'):
    '''
    Returns a `dict` generated by reading the file at `path`, and then parsing
    it as JSON. This will throw if the file does not exist, cannot be read, or
    cannot be parsed as JSON.
    The `encoding` parameter is used when initially reading the file.
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)
    assert isinstance(encoding, str), 'encoding must be a str: %r' % (encoding)

    if not is_file(path):
        logger.warning('path does not seem to refer to a valid file: %s', path)
        # but fall through and try anyway

    logger.debug(
        'attempting to parse file with path, encoding: %s, %s', path, encoding,
    )
    with open(path, encoding=encoding) as f:
        file_data = json.load(f)

    logger.debug('successfully parsed json file')
    return file_data


def save_json_file(fp, data, encoding='utf-8'):
    '''
    Serializes and writes out `data` to `fp`. The data should be provided as
    a `dict`, and will be serialized to a JSON string. The `fp` parameter
    should support a `write` method.
    The `encoding` parameter is used when encoding the serialized data.
    '''
    json_str = json.dumps(data)
    json_bytes = json_str.encode(encoding=encoding)
    fp.write(json_bytes)


def resolve_abspath(path, start=None):
    '''
    Resolves `path` to an absolute path. If the path is already an absolute
    path, it is returned as-is. Otherwise, it is joined to the `start` path,
    which is assumed to be an absolute path.
    If `start` is not provided, the current working directory is used.
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)

    if os.path.isabs(path):
        logger.debug('path is already absolute: %s', path)
        return path

    logger.debug('path is not absolute, need to resolve it')
    if start is None:
        start = os.getcwd()
        logger.debug('using working directory for relative paths: %s', start)
    assert isinstance(start, str), 'start must be a str: %r' % (start)

    logger.debug('joining path, start: %s, %s', path, start)
    return os.path.join(path, start)


def resolve_binary_path(binpath, workingdir=None, *pathdirs):
    '''
    Resolves the binary path `binpath` to an absolute path based on the
    supplied parameters. The following rules are applied until a path is found:
    1.  If it is already an absolute path, it is returned as-is.
    2.  If a file exists at the location relative to the working directory,
        then the absolute path to that file is returned. When workingdir is
        `None`, the current working directory is used (probably '.').
    3.  For each path directory in pathdirs, apply same relative location step
        as above. Only the first match will be returned, even if there would be
        more matches. When no pathdirs are provided, directories in the PATH
        environment variable are used.
    If no path is found, this will return `None`.
    '''
    assert isinstance(binpath, str), 'binpath must be a str: %r' % binpath

    if os.path.isabs(binpath):
        logger.debug(
            'binpath already absolute, returning as-is: %r', binpath
        )
        return binpath

    if workingdir is None:
        curdir = os.curdir
        workingdir = curdir
        logger.debug('filling in current working directory: %s', curdir)

    if not pathdirs:
        rawpath = os.getenv('PATH', default=None)
        if rawpath is None:
            logger.warning('cannot read PATH environment variable, might not '
                           'be able to resolve binary paths correctly')
            # just in case, assign it a dummy iterable value too
            pathdirs = tuple()
        else:
            assert isinstance(rawpath, str), \
                '[internal] rawpath from os.getenv is not a str: %r' % rawpath
            pathdirs = rawpath.split(os.path.pathsep)

    def generate_binpaths():
        '''
        Provides an iterator for all possible absolute locations for binpath.
        Platform dependent suffixes are automatically added, if applicable.
        '''
        should_add_win_exts = os.name == 'nt'
        win_exts = ['.exe', '.cmd', '.bat']
        for pathdir in itertools.chain([workingdir], pathdirs):
            assert isinstance(pathdir, str), \
                '[internal] pathdir is not a str: %r' % pathdir
            yield os.path.join(pathdir, binpath)
            if should_add_win_exts:
                for win_ext in win_exts:
                    filebasename = '%s%s' % (binpath, win_ext)
                    yield os.path.join(pathdir, filebasename)
        # end of iteration
        yield None

    found_files = filter(os.path.isfile, generate_binpaths())

    result_binpath = None
    try:
        result_binpath = next(found_files)
    except StopIteration:
        logger.debug('%s not found in %s, %s', binpath, workingdir, pathdirs)
    else:
        logger.debug('%s found at %s', binpath, result_binpath)

    return result_binpath


def default_python_binary_path():
    '''
    Generates and returns a path to the python executable, as resolved by
    `resolve_binary_path`. This will automatically prefer pythonw in Windows.
    '''
    if os.name == 'nt':
        pythonw_binpath = resolve_binary_path('pythonw')
        if pythonw_binpath:
            return pythonw_binpath

    python_binpath = resolve_binary_path('python')
    if python_binpath:
        return python_binpath

    # best effort:
    return 'python'


def _split_path_components(path):
    '''
    Splits `path` into a list of path components. The resulting list will start
    with directory names, leading up to the basename of the path.
    e.g.    '/usr/lib' -> ['', usr', 'lib']
            'C:\\Users' -> ['C:', 'Users']
    '''
    assert isinstance(path, str), 'path must be a str: %r' % (path)
    primary_dirsep = os.sep
    secondary_dirsep = os.altsep

    if not secondary_dirsep:
        # easy case, only one directory separator, so split on it
        return path.split(primary_dirsep)

    # ugh, more complicated case
    # the file system might permit both directory separators
    # e.g.  'C:\\Program Files/Sublime Text 3'
    # need to split on both to get the correct result in that case...

    def _iter_components(path=path):
        current_path = path[:]
        while current_path:
            primary_position = current_path.find(primary_dirsep)
            secondary_position = current_path.find(secondary_dirsep)
            split_position = -1

            # `str.find` returns -1 if no match, so check that first
            if primary_position >= 0 and secondary_position >= 0:
                # both are present - figure out which is first
                if primary_position > secondary_position:
                    # secondary separator first - split on second
                    split_position = secondary_position
                else:
                    # primary separator first - split on first
                    split_position = primary_position
            elif primary_position >= 0:
                # primary separator only - split on it
                # technically we can just split on the one separator and
                # yield the list items, but meh
                split_position = primary_position
            elif secondary_position >= 0:
                split_position = secondary_position
            # else, nothing to split

            if split_position >= 0:
                # perform split from 0 to split_position (non-inclusive), and
                # from split_position+1 to the end
                head = (
                    current_path[:split_position]
                    if split_position > 0 else ''
                )
                tail = (
                    current_path[split_position + 1:]
                    if split_position < len(current_path) else ''
                )

                yield head
                current_path = tail
            else:
                yield current_path
                current_path = ''

    return list(_iter_components(path))


def _commonpath_polyfill(paths):
    '''
    Polyfill for `os.path.commonpath` (not available in Python 3.3).
    This method returns the common ancestor between all the given `paths`.

    Implementation note:
    This works by splitting the paths using directory separators, and then
    comparing each portion from left to right until a mismatch is found.
    This calls `os.path.commonprefix`, which doesn't necessarily result in a
    valid path. To get the valid path from it, we need to ensure that the
    string ends in a directory separator. Anything else is considered invalid.
    '''

    if not paths:
        raise ValueError('Paths are invalid: %r' % (paths))
    # NOTE : the `zip` logic below is slow... only do it if necessary:
    if len(paths) == 1:
        path = paths[0]
        logger.debug('only one path, returning it: %s', path)
        return path

    path_components = [_split_path_components(path) for path in paths]
    logger.debug(
        'calculated path components for all paths: %s', path_components
    )

    # bundle up the components so we traverse them one at a time
    # e.g.  [['usr', 'lib'], ['usr', 'bin']]
    #   ->  (('usr', 'usr'), ('lib', 'bin'))
    path_traverser = zip(*path_components)

    # now traverse them until there's a mismatch
    common_path_components = []
    for current_components in path_traverser:
        # `current_components` is a tuple of strings
        # e.g.  ('usr', 'usr', 'lib') from ['/usr', '/usr/bin', '/lib']
        if not current_components:
            break
        one_component = current_components[0]
        all_equal = all(map(
            lambda c: c == one_component, current_components
        ))

        if not all_equal:
            break

        # else, equal! record this component and move on
        common_path_components.append(one_component)

    logger.debug(
        'calculated common path components: %s', common_path_components
    )

    if not common_path_components:
        raise ValueError('Paths do not have a common ancestor')

    # ugh, `ntpath` won't join absolute paths correctly, so ensure that the
    # first item always ends in a directory separator
    common_path_components[0] += os.sep
    return os.path.join(*common_path_components)


def get_common_ancestor(paths, default=None):
    common_path = default
    try:
        # common_path = os.path.commonpath(paths)
        common_path = _commonpath_polyfill(paths)
    except ValueError as e:
        logger.debug(
            'invalid paths, cannot get common ancenstor: %s, %r',
            paths, e,
        )

    return common_path
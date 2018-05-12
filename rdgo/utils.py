# Copyright (C) 2015 Colin Walters <walters@verbum.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import six
import sys
import stat
import shutil
import errno
import subprocess
import os

def fatal(msg):
    sys.stderr.write(msg + '\n')
    sys.exit(1)

def log(msg):
    "Print to standard output and flush it"
    sys.stdout.write(msg)
    sys.stdout.write('\n')
    sys.stdout.flush()

def convert_key_pair_into_commands(key_value_pairs):
    """
    This command is mainly used for rpmdbuild-opts, where you have
    to wrap every options with only one single entry. (for passing into mockbuild)
    """
    output_string_list = []
    # Loop through the key_pair dictionary and extract them as commands
    for key, value in key_value_pairs.items():
        if not isinstance(key, str):
            raise TypeError("To pass options into rpmbuild, key itself has to be a string, Please check your yaml file definition")
        if not isinstance(value, str):
            raise TypeError("A non-string value is not allowed, Please check your yaml file definition")

        # Convert the key value pair into '--define key value"' command format
        # e.g a key, value: foo bar, will be evaluated into '--define "foo bar"'
        command = '--define "{} {}"'.format(key, value)
        output_string_list.append(command)
    output = " ".join(output_string_list)
    return output

def run_sync(args, **kwargs):
    """Wraps subprocess.check_call(), logging the command line too."""
    if isinstance(args, six.string_types):
        argstr = args
    else:
        uargs = []
        for arg in args:
            if isinstance(arg, six.binary_type):
                uargs.append(arg.decode('UTF-8'))
            else:
                uargs.append(arg)
        args = uargs
        print("{}".format(args))
        argstr = subprocess.list2cmdline(args)
    log("Running: {0}".format(argstr))
    subprocess.check_call(args, **kwargs)

def rmrf(path):
    try:
        stbuf = os.lstat(path)
    except OSError as e:
        return
    if stat.S_ISDIR(stbuf.st_mode):
        shutil.rmtree(path)
    else:
        try:
            os.unlink(path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

def hardlink_or_copy(src, dest):
    try:
        os.link(src, dest)
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
        shutil.copy(src,dest)

def ensuredir(path, with_parents=False):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

def ensure_clean_dir(path):
    rmrf(path)
    ensuredir(path)

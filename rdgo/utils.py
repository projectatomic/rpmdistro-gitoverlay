#!/usr/bin/env python
#
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

import sys
import stat
import shutil
import errno
import subprocess
import os

from gi.repository import GLib, Gio

def fatal(msg):
    print >>sys.stderr, msg
    sys.exit(1)

def log(msg):
    "Print to standard output and flush it"
    sys.stdout.write(msg)
    sys.stdout.write('\n')
    sys.stdout.flush()

def run_sync(args, **kwargs):
    """Wraps subprocess.check_call(), logging the command line too."""
    if isinstance(args, str) or isinstance(args, unicode):
        argstr = args
    else:
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


# Copyright (C) 2016 Colin Walters <walters@verbum.org>
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

import os
import argparse

from .utils import fatal, ensuredir, run_sync
from .basetask_resolve import BaseTaskResolve

class TaskClone(BaseTaskResolve):
    def __init__(self):
        BaseTaskResolve.__init__(self)

    def run(self, argv):
        parser = argparse.ArgumentParser(description="Create a new build directory inheriting sources (possibly with overrides)")
        parser.add_argument('srcdir', help='Path to source directory')
        parser.add_argument('--full', action='store_true', help='Create writable mirrors of source')

        opts = parser.parse_args(argv)

        if not os.path.isdir(opts.srcdir):
            fatal("Missing {}/src/ directory".format(opts.srcdir))

        should_not_exist_links = ['build']
        if not opts.full:
            should_not_exist_links.append('src')
        for link in should_not_exist_links:
            if os.path.islink(link):
                fatal("{}/ symlink already exists; workdir already initialized?".format(link))

        if not opts.full:
            for child in ['snapshot', 'overlay.yml']:
                os.symlink(opts.srcdir + '/' + child, child)
            print("Intialized build working directory inherting source from {}".format(opts.srcdir))
        else:
            for child in ['overlay.yml']:
                os.symlink(opts.srcdir + '/' + child, child)
            self.srcdir = self.workdir + '/src'
            self.lookaside_mirror = self.srcdir + '/lookaside'
            if os.path.exists(self.srcdir):
                fatal("src/ directory already exists; workdir already initialized?")
            ensuredir(self.srcdir)

            self._load_overlay()
            self._expand_overlay(parent_mirror=opts.srcdir + '/src')

            # Lookaside cache can just be hardlinks
            run_sync(['cp', '-al', opts.srcdir + '/src/lookaside', self.lookaside_mirror])
            run_sync(['rpmdistro-gitoverlay', 'resolve'])

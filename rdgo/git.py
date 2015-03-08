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

import os
import re
import collections
import shutil
import subprocess
import tempfile

from gi.repository import GLib, Gio, GSystem

from .utils import log, fatal, run_sync

def path_with_suffix(path, suffix):
    return os.path.dirname(path) + '/' + os.path.basename(path) + suffix

def rmrf(path):
    GSystem.shutil_rm_rf(Gio.File.new_for_path(path), None)

def make_absolute_url(parent, relpath):
    orig_parent = parent
    orig_relpath = relpath
    if parent.endswith('/'):
        parent = parent[0:-1]
    method_index = parent.find('://')
    assert method_index != -1
    first_slash = parent.find('/', method_index+3)
    assert first_slash != -1
    parent_path = parent[first_slash:]
    while relpath.startswith('../'):
        i = parent.rfind('/')
        if i == -1:
            fatal("Relative submodule path {0} is too long for parent {1}".format(orig_relpath, orig_parent))
        relpath = relpath[3:]
        parent = parent[0:i]
    parent = parent[0:first_slash] + parent
    if relpath == '':
        return parent
    return parent + '/' + relpath

GitSubmodule = collections.namedtuple('GitSubmodule',
                                      ['checksum', 'name', 'url'])

class GitMirror(object):
    _pathname_quote_re = re.compile(r'[/\.]')

    def __init__(self, mirrordir):
        self.mirrordir = mirrordir
        self.tmpdir = mirrordir + '/_tmp'

    def _get_mirrordir(self, uri, prefix=''):
        colon = uri.find('://')
        if colon >= 0:
            scheme = uri[0:colon]
            rest = uri[colon+3]
        else:
            scheme = 'file'
            if uri[0] == '/':
                rest = uri[1]
            else:
                ret = uri
        if prefix:
            prefix = prefix + '/'
        return self.mirrordir + '/' + prefix + scheme + '/' + rest

    def _git_revparse(self, gitdir, branch):
        return subprocess.check_output(['git', 'rev-parse', branch], cwd=gitdir).strip()

    def _list_submodules(self, gitdir, uri, branch):
        current_rev = self._git_revparse(gitdir, branch)
        tmpdir = tempfile.mkdtemp('', 'tmp-gitmirror', self.tmpdir)
        tmp_clone =  tmpdir + '/checkout'
        try:
            run_sync(['git', 'clone', '-q', '--no-checkout', gitdir, tmp_clone])
            run_sync(['git', 'checkout', '-q', '-f', current_rev], cwd=tmp_clone)
            proc = subprocess.Popen(['git', 'submodule', 'status'], cwd=tmp_clone,
                                    stdout=subprocess.PIPE)
            submodules = []
            for line in proc.stdout:
                line = line.strip()
                if line == '':
                    continue
                line = line[1:]
                sub_checksum, sub_name, rest = line.split(' ', 2)
                sub_url = subprocess.check_output(['git', 'config', '-f', '.gitmodules',
                                                   'submodule.{0}.url'.format(sub_name)],
                                                  cwd=tmp_clone)
                submodules.append(GitSubmodule(sub_checksum, sub_name, sub_url))
        finally:
            rmrf(tmpdir)
        return submodules

    def mirror(self, url, branch_or_tag,
               fetch=False, fetch_continue=False):
        mirrordir = self._get_mirrordir(url)
        tmp_mirror = os.path.dirname(mirrordir) + '/' + os.path.basename(mirrordir) + '.tmp'
        did_update = False
        
        rmrf(tmp_mirror)
        if not os.path.isdir(mirrordir):
            run_sync(['git', 'clone', '--mirror', url, tmp_mirror])
            run_sync(['git', 'config', 'gc.auto', '0'], cwd=tmp_mirror)
            os.rename(tmp_mirror, mirrordir)
        elif fetch:
            run_sync(['git', 'fetch'], cwd=mirrordir)
        
        for module in self._list_submodules(mirrordir, url, branch_or_tag):
            log("Processing {0}".format(module))
            sub_url = module.url
            if sub_url.startswith('../'):
                sub_url = make_absolute_url(url, sub_url)
            self.mirror(sub_url, module.checksum,
                        fetch=fetch, fetch_continue=fetch_continue)

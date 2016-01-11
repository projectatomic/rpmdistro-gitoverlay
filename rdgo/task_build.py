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

from __future__ import print_function

import os
import argparse
import json
import StringIO
import subprocess
import shutil
import hashlib
import yaml
import tempfile
import copy

from .swappeddir import SwappedDirectory
from .utils import log, fatal, ensuredir, rmrf, ensure_clean_dir, run_sync, hardlink_or_copy
from .task import Task
from .git import GitMirror
from .mockchain import MockChain

def require_key(conf, key):
    try:
        return conf[key]
    except KeyError, e:
        fatal("Missing config key {0}".format(key))

class TaskBuild(Task):

    def _assert_get_one_child(self, path):
        results = os.listdir(path)
        if len(results) == 0:
            fatal("No files found in {0}".format(path))
        if len(results) > 1:
            fatal("Too many files found in {0}: {1}".format(path, results))
        return path + '/' + results[0]

    def _json_hash(self, dictval):
        """Kind of a hack, but it works."""
        serialized = json.dumps(dictval, sort_keys=True)
        h = hashlib.sha256()
        h.update(serialized)
        return h.hexdigest()

    def _move_logs_to_logdir(self, builddir, logdir):
        for dname in os.listdir(builddir):
            dpath = os.path.join(builddir, dname)
            statusjson = dpath + '/status.json'
            if os.path.isfile(statusjson):
                with open(statusjson) as f:
                    status = json.load(f)
                success = (status['status'] == 'success')
                if success:
                    sublogdir = logdir + '/success/' + dname
                else:
                    sublogdir = logdir + '/failed/' + dname
                ensure_clean_dir(sublogdir)
                for subname in os.listdir(dpath):
                    subpath = dpath + '/' + subname
                    if subname.endswith(('.json', '.log')):
                        shutil.move(subpath, sublogdir + '/' + subname)

    def _copy_previous_build(self, cachedstate):
        cached_dirname = cachedstate['dirname']
        oldrpmdir = self.builddir.path + '/' + cached_dirname
        newrpmdir = self.newbuilddir + '/' + cached_dirname
        subprocess.check_call(['cp', '-al', oldrpmdir, newrpmdir])

    def run(self, argv):
        parser = argparse.ArgumentParser(description="Build RPMs")
        parser.add_argument('--tempdir', action='store', default=None,
                            help='Path to directory for temporary working files')
        parser.add_argument('--touch-if-changed', action='store', default=None,
                            help='Create or update timestamp on target path if a change occurred')
        parser.add_argument('--logdir', action='store', default=None,
                            help='Store build logs in this directory')
        opts = parser.parse_args(argv)

        snapshot = self.get_snapshot()

        root = require_key(snapshot, 'root')
        root_mock = require_key(root, 'mock')

        self.tmpdir = opts.tempdir

        self.mirror = GitMirror(self.workdir + '/src')
        self.snapshotdir = self.workdir + '/snapshot'
        self.builddir = SwappedDirectory(self.workdir + '/build')

        self.newbuilddir = self.builddir.prepare()

        # Support including mock .cfg files next to overlay.yml
        if root_mock.endswith('.cfg') and not os.path.isabs(root_mock):
            target_root_mock = os.path.join(self.workdir, root_mock)
            if os.path.isfile(target_root_mock):
                root_mock = target_root_mock
            else:
                contextdir = os.path.dirname(os.path.realpath(self.workdir + '/overlay.yml'))
                root_mock = os.path.join(contextdir, root_mock)

        pkglist = []

        oldcache_path = self.builddir.path + '/buildstate.json'
        oldcache = {}
        if os.path.exists(oldcache_path):
            with open(oldcache_path) as f:
                oldcache = json.load(f)
        newcache = {}
        newcache_path = self.newbuilddir + '/buildstate.json'

        old_component_count = len(oldcache)
        new_component_count = len(snapshot['components'])

        need_build = False
        need_createrepo = old_component_count != new_component_count
        for component in snapshot['components']:
            component_hash = self._json_hash(component)
            distgit_name = component['pkgname']
            cachedstate = oldcache.get(distgit_name)
            if cachedstate is not None:
                cached_dirname = cachedstate['dirname']
                if cachedstate['hashv0'] == component_hash:
                    log("Reusing cached build: {0}".format(cached_dirname))
                    self._copy_previous_build(cachedstate)
                    newcache[distgit_name] = cachedstate
                    continue
                elif component.get('self-buildrequires', False):
                    log("Copying previous cached build for self-BR: {0}".format(cached_dirname))
                    self._copy_previous_build(cachedstate)
            srcsnap = component['srcsnap']
            newcache[distgit_name] = {'hashv0': component_hash,
                                      'dirname': srcsnap.replace('.srcsnap','')}
            pkglist.append(self.snapshotdir + '/' + srcsnap + '/')
            need_build = True
            need_createrepo = True

        if need_build:
            mc = MockChain(root_mock, self.newbuilddir)
            rc = mc.build(pkglist)
            if opts.logdir is not None:
                ensure_clean_dir(opts.logdir)
                self._move_logs_to_logdir(self.newbuilddir, opts.logdir)
            if rc != 0:
                fatal("mockchain exited with code {0}".format(rc))
        elif need_createrepo:
            log("No build neeeded, but component set changed")

        if need_createrepo:
            run_sync(['createrepo_c', '--no-database', '--update', '.'], cwd=self.newbuilddir)
            # No idea why createrepo is injecting this
            with open(newcache_path, 'w') as f:
                json.dump(newcache, f, sort_keys=True)

            self.builddir.commit()
            if opts.touch_if_changed:
                # Python doesn't bind futimens() - http://stackoverflow.com/questions/1158076/implement-touch-using-python
                with open(opts.touch_if_changed, 'a'):
                    log("Updated timestamp of {}".format(opts.touch_if_changed))
                    os.utime(opts.touch_if_changed, None)
            log("Success!")
        else:
            self.builddir.abandon()
            log("No changes.")



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
import subprocess
import shutil
import hashlib

from .swappeddir import SwappedDirectory
from .utils import log, fatal, rmrf, ensure_clean_dir, run_sync
from .task import Task
from .git import GitMirror
from .mockchain import MockChain, SRPMBuild

def require_key(conf, key):
    try:
        return conf[key]
    except KeyError:
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

    def _postprocess_results(self, builddir, snapshot=None, needed_builds=None, newcache=None, logdir=None):
        # We always dump the partial build results, so the next build can pick them up
        retained = []
        for component in snapshot['components']:
            distgit_name = component['pkgname']
            if distgit_name not in needed_builds:
                continue
            cachedstate = newcache[distgit_name]
            cached_dirname = cachedstate['dirname']
            buildpath = builddir + '/' + cached_dirname
            statusjson = buildpath + '/status.json'
            success = False
            if os.path.isfile(statusjson):
                with open(statusjson) as f:
                    status = json.load(f)
                    success = (status['status'] == 'success')
            if logdir is not None:
                if success:
                    sublogdir = logdir + '/success/' + distgit_name
                else:
                    sublogdir = logdir + '/failed/' + distgit_name
                ensure_clean_dir(sublogdir)
                for subname in os.listdir(buildpath):
                    subpath = buildpath + '/' + subname
                    if subname.endswith(('.json', '.log')):
                        shutil.move(subpath, sublogdir + '/' + subname)
            if not success:
                del newcache[distgit_name]
            else:
                retained.append(distgit_name)
        if len(retained) > 0:
            log("Retaining partial sucessful builds: {0}".format(' '.join(retained)))

    def _copy_previous_build(self, cachedstate, fromdir):
        cached_dirname = cachedstate['dirname']
        oldrpmdir = fromdir + '/' + cached_dirname
        newrpmdir = self.newbuilddir + '/' + cached_dirname
        subprocess.check_call(['cp', '-al', oldrpmdir, newrpmdir])

    def run(self, argv):
        parser = argparse.ArgumentParser(description="Build RPMs")
        parser.add_argument('--tempdir', action='store', default=None,
                            help='Path to directory for temporary working files')
        parser.add_argument('--arch', action='store', default=os.uname()[4],
                            help='Value for $arch variable, substituted in mock root')
        parser.add_argument('--touch-if-changed', action='store', default=None,
                            help='Create or update timestamp on target path if a change occurred')
        parser.add_argument('--logdir', action='store', default=None,
                            help='Store build logs in this directory')
        opts = parser.parse_args(argv)

        snapshot = self.get_snapshot()

        root = require_key(snapshot, 'root')
        root_mock = require_key(root, 'mock').replace('$arch', opts.arch)
        
        self.tmpdir = opts.tempdir

        self.mirror = GitMirror(self.workdir + '/src')
        self.snapshotdir = self.workdir + '/snapshot'
        self.builddir = SwappedDirectory(self.workdir + '/build')
        # Contains any artifacts from a previous run that did succeed
        self.partialbuilddir = self.workdir + '/build.partial'
        
        self.newbuilddir = self.builddir.prepare(save_partial_dir=self.partialbuilddir)

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
        partial_path = self.partialbuilddir + '/buildstate.json'
        partial_cache = {}
        if os.path.exists(partial_path):
            with open(partial_path) as f:
                partial_cache = json.load(f)
        newcache = {}
        newcache_path = self.newbuilddir + '/buildstate.json'

        old_component_count = len(oldcache)
        new_component_count = len(snapshot['components'])

        needed_builds = set()
        need_createrepo = old_component_count != new_component_count
        for component in snapshot['components']:
            component_hash = self._json_hash(component)
            distgit_name = component['pkgname']
            cache_misses = []
            for (cache, cache_parent, cache_description) in [(oldcache, self.builddir.path, 'previous'),
                                                             (partial_cache, self.partialbuilddir, 'partial')]:
                cachedstate = cache.get(distgit_name)
                if cachedstate is None:
                    continue

                cached_dirname = cachedstate['dirname']
                if component.get('self-buildrequires', False):
                    log("Copying previous {1} build due to self-BuildRequires: {0}".format(cached_dirname, cache_description))
                    self._copy_previous_build(cachedstate, cache_parent)
                    break
                elif cachedstate['hashv0'] == component_hash:
                    log("Reusing cached {1} build: {0}".format(cached_dirname, cache_description))
                    self._copy_previous_build(cachedstate, cache_parent)
                    newcache[distgit_name] = cachedstate
                    break
                else:
                    cache_misses.append(cache_description)

            if newcache.get(distgit_name) is not None:
                continue

            if len(cache_misses) > 0:
                log("Cache miss for {0} in: {1}".format(distgit_name, ' '.join(cache_misses)))
            else:
                log("No cached state for {0}".format(distgit_name))

            srcsnap = component['srcsnap']
            newcache[distgit_name] = {'hashv0': component_hash,
                                      'dirname': srcsnap.replace('.srcsnap','')}
            pkglist.append(SRPMBuild(self.snapshotdir + '/' + srcsnap + '/',
                                     component['rpmwith'], component['rpmwithout']))
            needed_builds.add(distgit_name)
            need_createrepo = True

        # At this point we've consumed any previous partial results, so clean up the dir.
        rmrf(self.partialbuilddir)

        if len(needed_builds) > 0:
            mc = MockChain(root_mock, self.newbuilddir)
            rc = mc.build(pkglist)
            if opts.logdir is not None:
                ensure_clean_dir(opts.logdir)
            self._postprocess_results(self.newbuilddir, snapshot=snapshot, needed_builds=needed_builds,
                                      newcache=newcache, logdir=opts.logdir)
            with open(newcache_path, 'w') as f:
                json.dump(newcache, f, sort_keys=True)
            if rc != 0:
                fatal("{0} failed: mockchain exited with code {1}".format(os.path.basename(self.newbuilddir), rc))
        elif need_createrepo:
            log("No build neeeded, but component set changed")

        if need_createrepo:
            run_sync(['createrepo_c', '--no-database', '--update', '.'], cwd=self.newbuilddir)
            if len(needed_builds) == 0:
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

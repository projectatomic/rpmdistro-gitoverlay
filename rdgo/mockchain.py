# by skvidal@fedoraproject.org
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
# copyright 2012 Red Hat, Inc.

# SUMMARY
# mockchain
# take a mock config and a series of srpms
# rebuild them one at a time
# adding each to a local repo
# so they are available as build deps to next pkg being built
from __future__ import print_function
try:
    from six.moves.urllib_parse import urlsplit  # pylint: disable=no-name-in-module
except ImportError:
    from urlparse import urlsplit  # noqa
import sys
import subprocess
import json
import os
import tempfile
import shutil
import re

import mockbuild.util

from . import specfile 
from .utils import fatal, ensuredir, run_sync, rmrf

# all of the variables below are substituted by the build system
__VERSION__ = "unreleased_version"
SYSCONFDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "..", "etc")
PYTHONDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
MOCKCONFDIR = os.path.join(SYSCONFDIR, "mock")
# end build system subs

# This variable is global as it's set by `eval`ing the mock config file =(
config_opts = {}

def log(msg):
    print(msg)

def createrepo(path):
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm = ['/usr/bin/createrepo_c', '--update', path]
    else:
        comm = ['/usr/bin/createrepo_c', path]
    run_sync(comm)

REPOS_ID = []
def generate_repo_id(baseurl):
    """ generate repository id for yum.conf out of baseurl """
    repoid = "/".join(baseurl.split('//')[1:]).replace('/', '_')
    repoid = re.sub(r'[^a-zA-Z0-9_]', '', repoid)
    suffix = ''
    i = 1
    while repoid + suffix in REPOS_ID:
        suffix = str(i)
        i += 1
    repoid = repoid + suffix
    REPOS_ID.append(repoid)
    return repoid

def add_local_repo(infile, destfile, baseurl, repoid=None):
    """take a mock chroot config and add a repo to it's yum.conf
       infile = mock chroot config file
       destfile = where to save out the result
       baseurl = baseurl of repo you wish to add"""
    global config_opts

    # What's going on here is we're dynamically executing the config
    # file as code, resetting any previous modifications to the `config_opts`
    # variable.
    with open(infile) as f:
        code = compile(f.read(), infile, 'exec')
    exec(code)

    # Add overrides to the default mock config here:
    # Ensure we're using the priorities plugin
    config_opts['priorities.conf'] = '\n[main]\nenabled=1\n'
    config_opts['yum.conf'] = config_opts['yum.conf'].replace('[main]\n', '[main]\nplugins=1\n')

    if not repoid:
        repoid = generate_repo_id(baseurl)
    else:
        REPOS_ID.append(repoid)
    localyumrepo = """
[%s]
name=%s
baseurl=%s
enabled=1
skip_if_unavailable=1
metadata_expire=30
cost=1
priority=1
""" % (repoid, baseurl, baseurl)
    config_opts['yum.conf'] += localyumrepo
    br_dest = open(destfile, 'w')
    for k, v in list(config_opts.items()):
        br_dest.write("config_opts[%r] = %r\n" % (k, v))
    br_dest.close()

def postprocess_mock_resultdir(resdir, success):
    statelog = resdir + '/state.log'
    status = 'unknown'
    with open(statelog) as f:
        for line in f:
            if line.find('Start: build setup ') >= 0:
                status = 'root-failed'
            elif line.find('Start: rpmbuild ') >= 0:
                status = 'build-failed'
            elif line.find('Finish: rpmbuild ') >= 0:
                status = 'expected-success'
    if status == 'build-failed':
        with open(resdir + '/build.log') as f:
            for line in f:
                if line.startswith('error: '):
                    sys.stderr.write(line)
    elif success:
        assert status == 'expected-success'
        status = 'success'
    if not success and status == 'unknown':
        status = 'unknown-failed'
    with open(resdir + '/status.json', 'w') as f:
        json.dump({'status': status}, f)

class MockChain(object):
    def __init__(self, root, local_repo):
        self.root = root
        self.local_repo = local_repo

        self._config_path = None

        mock_pkgpythondir = None
        r = re.compile('^PKGPYTHONDIR="([^"]+)"')
        with open('/usr/sbin/mock') as f:
            for line in f:
                m = r.search(line)
                if m:
                    mock_pkgpythondir = m.group(1)
                    break
        if mock_pkgpythondir is None:
            fatal("Failed to parse PKGPYTHONDIR from /usr/sbin/mock")

        global config_opts
        config_opts = mockbuild.util.load_config('/etc/mock', self.root, None, __VERSION__, mock_pkgpythondir)

        self._uniqueext = 'mockchain-{}'.format(os.getpid())

        self._local_tmp_dir = tempfile.mkdtemp('mockchain')

        if not os.path.exists(self.local_repo):
            os.makedirs(self.local_repo, mode=0o755)

        log("results dir: %s" % self.local_repo)
        self._config_path = os.path.normpath(self._local_tmp_dir + '/configs/' + config_opts['chroot_name'] + '/')

        if not os.path.exists(self._config_path):
            os.makedirs(self._config_path, mode=0o755)
        log("config dir: %s" % self._config_path)

        # Generate a new config
        self._mockcfg_path = os.path.join(self._config_path, "{0}.cfg".format(config_opts['chroot_name']))
        add_local_repo(config_opts['config_file'], self._mockcfg_path, 'file://' + self.local_repo, 'local_build_repo')

        # these files needed from the mock.config dir to make mock run
        for fn in ['site-defaults.cfg', 'logging.ini']:
            pth = '/etc/mock/' + fn
            shutil.copyfile(pth, self._config_path + '/' + fn)

        # createrepo on it
        createrepo(self.local_repo)

    def add_repo(self, url):
        add_local_repo(config_opts['config_file'], self._mockcfg_path, url)

    def _get_mock_base_argv(self):
        return ['/usr/bin/mock',
                '--configdir', self._config_path,
                '--uniqueext', self._uniqueext, '-r', self._mockcfg_path]

    def _run_mock_sync(self, *argv):
        argv = self._get_mock_base_argv() + list(argv)
        run_sync(argv)

    def do_clean_root(self):
        self._run_mock_sync('--clean')

    def do_one_build(self, pkg):
        # returns 0, cmd, out, err = failure
        # returns 1, cmd, out, err  = success
        # returns 2, None, None, None = already built

        is_srcsnap = pkg.endswith('/')

        if is_srcsnap:
            pdn = os.path.basename(pkg.replace('.srcsnap/', ''))
            srpm = None
        else:
            pdn = os.path.basename(pkg).replace('.temp.src.rpm', '')
            srpm = pkg
        resdir = '%s/%s' % (self.local_repo, pdn)
        resdir = os.path.normpath(resdir)
        resdir_src = resdir + '/srpm'
        ensuredir(resdir_src)

        success_file = resdir + '/success'
        fail_file = resdir + '/fail'

        if os.path.exists(success_file):
            return 2, None, None, None

        # clean it up if we're starting over :)
        if os.path.exists(fail_file):
            os.unlink(fail_file)

        if is_srcsnap:
            pkgdir = pkg[:-1]
            spec_fn = pkg + '/' + specfile.spec_fn(spec_dir=pkg)
            self._run_mock_sync('--old-chroot',
                                '--yum',
                                '--buildsrpm',
                                '--spec', spec_fn,
                                '--sources', pkgdir,
                                '--resultdir', resdir_src,
                                '--no-cleanup-after')
            for n in os.listdir(resdir_src):
                if n.endswith('.src.rpm'):
                    srpm = resdir_src + '/' + n
                    break
            if srpm is None:
                fatal("Failed to find .src.rpm in {0}".format(resdir_src))
            self.do_clean_root()

        mockcmd = self._get_mock_base_argv()
        mockcmd.extend(['--nocheck',  # Tests should run after builds
                        '--yum',
                        '--resultdir', resdir,
                        '--no-cleanup-after'])
        mockcmd.append(srpm)
        print('Executing: {0}'.format(subprocess.list2cmdline(mockcmd)))
        cmd = subprocess.Popen(mockcmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        out, err = cmd.communicate()
        success = cmd.returncode == 0
        postprocess_mock_resultdir(resdir, success)

        if success:
            if 'PRESERVE_TEMP' not in os.environ:
                rmrf(srpm)

        ret = 1 if success else 0
        return ret, cmd, out, err

    def build(self, pkgs):
        for pkg in pkgs:
            if not pkg.endswith(('.src.rpm', '/')):
                fatal("%s doesn't appear to be an rpm or srcsnap directory - skipping" % pkg)

        downloaded_pkgs = {}
        built_pkgs = []
        try_again = True
        to_be_built = pkgs
        return_code = 0
        num_of_tries = 0
        while try_again:
            num_of_tries += 1
            failed = []
            for pkg in to_be_built:
                log("Start build: %s" % pkg)
                ret, cmd, out, err = self.do_one_build(pkg)
                log("End build: %s" % pkg)
                if ret == 0:
                    failed.append(pkg)
                    log("Error building %s." % os.path.basename(pkg))
                    if len(pkgs) > 1:
                        log("Will try to build again (if some other package will succeed).")
                        if 'PRESERVE_TEMP' not in os.environ:
                            self.do_clean_root()
                    else:
                        if 'PRESERVE_TEMP' not in os.environ:
                            self.do_clean_root()
                elif ret == 1:
                    log("Success building %s" % os.path.basename(pkg))
                    self.do_clean_root()
                    built_pkgs.append(pkg)
                    # createrepo with the new pkgs
                    createrepo(self.local_repo)
                elif ret == 2:
                    log("Skipping already built pkg %s" % os.path.basename(pkg))

            if failed:
                if len(failed) != len(to_be_built):
                    to_be_built = failed
                    try_again = True
                    log('Some package succeeded, some failed.')
                    log('Trying to rebuild %s failed pkgs, because --recurse is set.' % len(failed))
                else:
                    log("Tried %s times - following pkgs could not be successfully built:" % num_of_tries)
                    for pkg in failed:
                        msg = pkg
                        if pkg in downloaded_pkgs:
                            msg = downloaded_pkgs[pkg]
                        log(msg)
                    try_again = False
                    return_code = 2
            else:
                try_again = False
                if failed:
                    return_code = 2

        log("Results out to: %s" % self.local_repo)
        log("Pkgs built: %s" % len(built_pkgs))
        if built_pkgs:
            if failed:
                if len(built_pkgs):
                    log("Some packages successfully built in this order:")
            else:
                log("Packages successfully built in this order:")
            for pkg in built_pkgs:
                log(pkg)
        return return_code

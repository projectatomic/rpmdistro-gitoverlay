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
import json
import pwd
import collections
import sys
import argparse
if sys.version_info[0] < 3:
    import ConfigParser
else:
    import configparser
import subprocess
import errno
import shutil
import yaml
import tempfile
import copy

# We don't have this on Travis (Ubuntu)...should probably make it optional.
import pyrpkg # pylint: disable=import-error
from pyrpkg.cli import cliClient # pylint: disable=import-error
from pyrpkg.sources import SourcesFile # pylint: disable=import-error

from .utils import log, fatal, ensuredir, rmrf, ensure_clean_dir, run_sync, hardlink_or_copy
from .task import Task
from . import specfile 
from .git import GitRemote, GitMirror

def require_key(conf, key):
    try:
        return conf[key]
    except KeyError as e:
        fatal("Missing config key {0}".format(key))

class TaskResolve(Task):
    def __init__(self):
        Task.__init__(self)
        self._srpm_mock_initialized = None
        self._valid_source_htypes = ['md5']

    def _json_dumper(self, obj):
        if isinstance(obj, GitRemote):
            return obj.url
        else:
            return obj

    def _get_rpkg(self, distgit, cwd):
        rpkgconfig = ConfigParser.SafeConfigParser()
        pkgtype = 'fedpkg'
        # Yes, awful hack.
        if distgit['src'].url.find('pkgs.devel.redhat.com') != -1:
            pkgtype = 'rhpkg'
        rpkgconfig.read('/etc/rpkg/{0}.conf'.format(pkgtype))
        rpkgconfig.add_section(os.path.basename(cwd))
        rpkg = cliClient(rpkgconfig, pkgtype)
        rpkg.do_imports(site=pkgtype)
        rpkg.args = rpkg.parser.parse_args(['--path=' + cwd, 'sources'])
        return rpkg
        
    def _url_to_projname(self, url):
        rcolon = url.rfind(':')
        rslash = url.rfind('/')
        basename = url[max(rcolon, rslash)+1:]
        if basename.endswith('.git'):
            return basename[0:-4]
        return basename

    def _prepend_workdir(self, val):
        if not val:
            return None
        return self.workdir + '/' + val

    def _expand_srckey(self, component, key):
        url = component[key]
        aliases = self._overlay.get('aliases', [])
        for alias in aliases:
            name = alias['name']
            namec = name + ':'
            if not url.startswith(namec):
                continue
            url = alias['url'] + url[len(namec):]
            return GitRemote(url, self._prepend_workdir(alias.get('cacertpath')))
        return GitRemote(url)

    def _ensure_key_or(self, dictval, key, value):
        v = dictval.get(key)
        if v is not None:
            return v
        dictval[key] = value
        return value

    def _one_of_keys(self, dictval, first, *args):
        v = dictval.get(first)
        if v is not None:
            return v
        for k in args:
            v = dictval.get(k)
            if v is not None:
                return v
        return None

    def _expand_component(self, component):
        for key in component:
            if key not in ['src', 'spec', 'distgit', 'tag', 'branch', 'freeze', 'self-buildrequires']:
                fatal("Unknown key {0} in component: {1}".format(key, component))
        # 'src' and 'distgit' mappings
        src = component.get('src')
        if src is None:
            fatal("Component {0} is missing 'src'")

        spec = component.get('spec')
        if spec is not None:
            if spec == 'internal':
                pass
            else:
                raise ValueError('Unknown spec type {0}'.format(spec))
            
        if src != 'distgit':
            component['src'] = self._expand_srckey(component, 'src')
            name = self._ensure_key_or(component, 'name', self._url_to_projname(component['src'].url))
            if spec != 'internal':
                distgit = self._ensure_key_or(component, 'distgit', {})
            else:
                distgit = {}
        else:
            del component['src']
            distgit = component.get('distgit')
            if distgit is None:
                fatal("Component {0} is missing 'distgit'")
            name = distgit.get('name')
            if name is None:
                fatal("Component {0} is missing 'distgit/name'")
            self._ensure_key_or(component, 'name', name)

        pkgname_default = name

        # TODO support pulling VCS from distgit
        
        # tag/branch defaults
        if component.get('tag') is None:
            component['branch'] = component.get('branch', 'master')

        if spec != 'internal':
            pkgname_default = self._ensure_key_or(distgit, 'name', pkgname_default)
            distgit['src'] = self._ensure_key_or(distgit, 'src', 
                                                 self._distgit_prefix + ':' + distgit['name'])
            distgit['src'] = self._expand_srckey(distgit, 'src')

            if distgit.get('tag') is None:
                distgit['branch'] = distgit.get('branch', 'master')

        for key in distgit:
            if key not in ['patches', 'src', 'name', 'tag', 'branch', 'freeze']:
                fatal("Unknown key {0} in component/distgit: {1}".format(key, component))

        self._ensure_key_or(component, 'pkgname', pkgname_default)

    def _tar_czf_with_prefix(self, dirpath, prefix, output):
        dn = os.path.dirname(dirpath)
        bn = os.path.basename(dirpath)
        run_sync(['tar', '--exclude-vcs', '-czf', output, '--transform', 's,^' + bn + ',' + prefix + ',', bn],
                 cwd=dn)

    def _strip_all_prefixes(self, s, prefixes):
        for prefix in prefixes:
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s

    def _rpm_verrel(self, component, upstream_tag, upstream_rev, distgit_desc):
        rpm_version = upstream_tag or '0'
        rpm_version = self._strip_all_prefixes(rpm_version, ['v', component['pkgname'] + '-'])
        rpm_version = rpm_version.replace('-', '.')
        gitdesc = upstream_rev or ''
        if distgit_desc is not None:
            if gitdesc != '':
                gitdesc += '.'
            gitdesc += distgit_desc.replace('-', '.')
        return [rpm_version, gitdesc]

    def _generate_srcsnap_impl(self, component, upstream_tag, upstream_rev, upstream_co,
                               distgit_desc, distgit_co, target):
        distgit = component.get('distgit')
        if distgit is not None:
            patches_action = distgit.get('patches', None)
        else:
            patches_action = None

        upstream_desc = upstream_rev
        if upstream_tag is not None:
            upstream_desc = upstream_tag + '-' + upstream_desc

        [rpm_version, rpm_release] = self._rpm_verrel(component, upstream_tag, upstream_rev, distgit_desc)

        spec_fn = specfile.spec_fn(spec_dir=distgit_co)
        spec = specfile.Spec(distgit_co + '/' + spec_fn)

        if upstream_desc is not None:
            tar_dirname = '{0}-{1}'.format(component['name'], upstream_desc)
            tarname = tar_dirname + '.tar.gz'
            tmp_tarpath = distgit_co + '/' + tarname
            self._tar_czf_with_prefix(upstream_co, tar_dirname, tmp_tarpath)
            rmrf(upstream_co)
            has_zero = spec.get_tag('Source0', allow_empty=True) is not None
            source_tag = 'Source'
            if has_zero:
                source_tag += '0'
            spec.set_tag(source_tag, tarname)
            spec.set_tag('Version', rpm_version)
            spec.set_setup_dirname(tar_dirname)
        spec.set_tag('Release', rpm_release + '%{?dist}')
        # Anything useful there you should find in upstream dist-git or equivalent.
        spec.delete_changelog()
        # Forcibly override
        # spec.set_tag('Epoch', '99')
        if patches_action in (None, 'keep'):
            pass
        elif patches_action == 'drop':
            spec.wipe_patches()
        else:
            fatal("Component '{0}': Unknown patches action '{1}'".format(component['name'],
                                                                         patches_action))
        spec.save()
        spec._txt = '# NOTE: AUTO-GENERATED by rpmdistro-gitoverlay; DO NOT EDIT\n' + spec._txt

        sources_path = distgit_co + '/sources'
        if os.path.exists(sources_path):
            rpkg = self._get_rpkg(distgit, distgit_co)
            srcfile = SourcesFile(sources_path, rpkg.cmd.source_entry_type)
            for entry in srcfile.entries:
                # For now, enforce this due to paranoia about potential unsafe
                # code paths.
                if entry.hashtype not in self._valid_source_htypes:
                    fatal('Invalid hash type {0}'.format(entry.hashtype))
                hashtypepath = self.lookaside_mirror + '/' + entry.hashtype
                ensuredir(hashtypepath)

                # Sanity check
                assert '/' not in entry.hash
                assert '/' not in entry.file

                hashprefixpath = hashtypepath + '/' + entry.hash[0:2]
                ensuredir(hashprefixpath)
                objectpath = hashprefixpath + '/' + entry.hash[2:]

                objectpath_tmp = objectpath + '.tmp'
                rmrf(objectpath_tmp)

                if not os.path.exists(objectpath):
                    print("Downloading source object for {0}: {1}".format(distgit['name'], entry.file))
                    rpkg.cmd.lookasidecache.download(distgit['name'],
                                                     entry.file, entry.hash,
                                                     objectpath_tmp,
                                                     hashtype=entry.hashtype)
                    os.rename(objectpath_tmp, objectpath)
                else:
                    print("Reusing cached source object for {0}: {1}".format(distgit['name'], entry.file))
                hardlink_or_copy(objectpath, distgit_co + '/' + entry.file)

        shutil.move(distgit_co, self.tmp_snapshotdir + '/' + target)

    def _generate_srcsnap(self, component):
        upstream_src = component.get('src')
        if upstream_src is not None:
            upstream_rev = component['revision']
            [upstream_tag, upstream_rev] = self.mirror.describe(upstream_src, upstream_rev)
            upstream_desc = upstream_rev
            if upstream_tag is not None:
                upstream_desc = upstream_tag + '-' + upstream_desc
        else:
            upstream_rev = upstream_tag = upstream_desc = None

        distgit = component.get('distgit')
        if distgit is not None:
            distgit_src = distgit['src']
            distgit_rev = distgit['revision']
            [distgit_tag, distgit_rev] = self.mirror.describe(distgit_src, distgit_rev)
            distgit_desc = distgit_rev
            if distgit_tag is not None:
                distgit_desc = distgit_tag + '-' + distgit_desc
        else:
            distgit_desc = None

        assert (upstream_desc or distgit_desc) is not None

        [rpm_version, rpm_release] = self._rpm_verrel(component, upstream_tag, upstream_rev, distgit_desc)

        srcsnap_name = "{0}-{1}-{2}.srcsnap".format(component['pkgname'], rpm_version, rpm_release)
        tmpdir = tempfile.mkdtemp('', 'rdgo-srpms', self.tmpdir)
        try:
            if upstream_src is not None:
                upstream_co = tmpdir + '/' + component['name']
                self.mirror.checkout(upstream_src, upstream_rev, upstream_co)
            else:
                upstream_co = None

            if distgit is not None:
                distgit_topdir = tmpdir + '/' + 'distgit'
                ensure_clean_dir(distgit_topdir)
                # Create a directory whose name matches the module
                # name, which helps fedpkg/rhpkg.
                distgit_co = distgit_topdir + '/' + distgit['name']
                self.mirror.checkout(distgit_src, distgit_rev, distgit_co)
            else:
                spec_paths = [upstream_co, upstream_co + '/packaging']
                specbasefn = component['pkgname'] + '.spec'
                specfn = None
                for path in spec_paths:
                    for name in [path + '/' + specbasefn, path + '/' + specbasefn + '.in']:
                        if os.path.isfile(name):
                            specfn = name
                            break
                    if specfn is not None:
                        break
                if specfn is None:
                    fatal("Failed to find .spec (or .spec.in) file")
                if specfn.endswith('.in'):
                    dest_specfn = tmpdir + '/' + os.path.basename(specfn[:-3])
                else:
                    dest_specfn = tmpdir
                shutil.copy2(specfn, dest_specfn)
                distgit_co = tmpdir

            self._generate_srcsnap_impl(component, upstream_tag, upstream_rev, upstream_co,
                                        distgit_desc, distgit_co,
                                        srcsnap_name)
        finally:
            if not 'PRESERVE_TEMP' in os.environ:
                rmrf(tmpdir)
        return srcsnap_name

    def run(self, argv):
        parser = argparse.ArgumentParser(description="Create snapshot.json")
        parser.add_argument('--tempdir', action='store', default=None,
                            help='Path to directory for temporary working files')
        parser.add_argument('--fetch-all', action='store_true', help='Fetch all git repositories')
        parser.add_argument('-f', '--fetch', action='append', default=[],
                            help='Fetch the specified git repository')
        parser.add_argument('--touch-if-changed', action='store', default=None,
                            help='Create or update timestamp on target path if a change occurred')

        opts = parser.parse_args(argv)

        srcdir = self.workdir + '/src'
        if not os.path.isdir(srcdir):
            fatal("Missing src/ directory; run 'rpmdistro-gitoverlay init'?")

        self.mirror = GitMirror(self.workdir + '/src')
        self.lookaside_mirror = self.workdir + '/src/lookaside'
        self.tmpdir = opts.tempdir

        self.old_snapshotdir = self.workdir + '/old-snapshot'
        self.snapshotdir = self.workdir + '/snapshot'
        self.tmp_snapshotdir = self.snapshotdir + '.tmp'
        ensure_clean_dir(self.tmp_snapshotdir)

        ensuredir(self.lookaside_mirror)

        ovlpath = self.workdir + '/overlay.yml'
        with open(ovlpath) as f:
            self._overlay = yaml.load(f)

        root = require_key(self._overlay, 'root')
        root_mock = require_key(root, 'mock')

        # Support including mock .cfg files next to overlay.yml
        if root_mock.endswith('.cfg') and not os.path.isabs(root_mock):
            target_root_mock = os.path.join(self.workdir, root_mock)
            if os.path.isfile(target_root_mock):
                root_mock = target_root_mock
            else:
                contextdir = os.path.dirname(os.path.realpath(self.workdir + '/overlay.yml'))
                root_mock = os.path.join(contextdir, root_mock)

        self._root_mock = root_mock
            
        self._distgit = require_key(self._overlay, 'distgit')
        self._distgit_prefix = require_key(self._distgit, 'prefix')

        expanded = copy.deepcopy(self._overlay)
        for component in expanded['components']:
            self._expand_component(component)
            ref = self._one_of_keys(component, 'freeze', 'branch', 'tag')
            do_fetch = opts.fetch_all or (component['name'] in opts.fetch)
            src = component.get('src')
            if src is not None:
                revision = self.mirror.mirror(src, ref, fetch=do_fetch)
                component['revision'] = revision

            distgit = component.get('distgit')
            if distgit is not None:
                ref = self._one_of_keys(distgit, 'freeze', 'branch', 'tag')
                do_fetch = opts.fetch_all or (distgit['name'] in opts.fetch)
                revision = self.mirror.mirror(distgit['src'], ref, fetch=do_fetch)
                distgit['revision'] = revision

            srcsnap = self._generate_srcsnap(component)
            component['srcsnap'] = os.path.basename(srcsnap)

        del expanded['aliases']

        expanded['00comment'] = 'Generated by rpmdistro-gitoverlay from overlay.yml: DO NOT EDIT!'

        snapshot_path = self.snapshotdir + '/snapshot.json'
        snapshot_tmppath = self.tmp_snapshotdir + '/snapshot.json'
        with open(snapshot_tmppath, 'w') as f:
            json.dump(expanded, f, indent=4, sort_keys=True, default=self._json_dumper)

        rmrf(self.old_snapshotdir)

        changed = True
        if (os.path.exists(snapshot_path) and
            subprocess.call(['cmp', '-s', snapshot_path, snapshot_tmppath]) == 0):
            changed = False
        if changed:
            try:
                os.rename(self.snapshotdir, self.old_snapshotdir)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
            os.rename(self.tmp_snapshotdir, self.snapshotdir)
            log("Wrote: " + self.snapshotdir)
            if opts.touch_if_changed:
                with open(opts.touch_if_changed, 'a'):
                    log("Updated timestamp of {}".format(opts.touch_if_changed))
                    os.utime(opts.touch_if_changed, None)
        else:
            rmrf(self.tmp_snapshotdir)
            log("No changes.")
                

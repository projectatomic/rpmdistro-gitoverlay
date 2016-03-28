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
import yaml
import copy

from .utils import fatal
from .task import Task
from .git import GitRemote, GitMirror

def require_key(conf, key):
    try:
        return conf[key]
    except KeyError:
        fatal("Missing config key {0}".format(key))

class BaseTaskResolve(Task):
    def __init__(self):
        Task.__init__(self)
        self._valid_source_htypes = ['md5']
        self._overlay = None
        self._distgit_prefix = None

    def _url_to_projname(self, url):
        rcolon = url.rfind(':')
        rslash = url.rfind('/')
        basename = url[max(rcolon, rslash)+1:]
        if basename.endswith('.git'):
            return basename[0:-4]
        return basename

    def _prepend_ovldatadir(self, val):
        if not val:
            return None
        return self._overlay_datadir + '/' + val

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

    def _expand_srckey(self, component, key):
        url = component[key]
        aliases = self._overlay.get('aliases', [])
        for alias in aliases:
            name = alias['name']
            namec = name + ':'
            if not url.startswith(namec):
                continue
            url = alias['url'] + url[len(namec):]
            return GitRemote(url, self._prepend_ovldatadir(alias.get('cacertpath')))
        return GitRemote(url)

    def _expand_component(self, component):
        for key in component:
            if key not in ['src', 'spec', 'distgit', 'tag', 'branch', 'freeze', 'self-buildrequires']:
                fatal("Unknown key {0} in component: {1}".format(key, component))
        # 'src' and 'distgit' mappings
        src = component.get('src')
        distgit = component.get('distgit')
        if src is None and distgit is None:
            fatal("Component {0} is missing 'src' or 'distgit'")

        spec = component.get('spec')
        if spec is not None:
            if spec == 'internal':
                pass
            else:
                raise ValueError('Unknown spec type {0}'.format(spec))
            
        # Canonicalize
        if src is None:
            component['src'] = src = 'distgit'
        if isinstance(distgit, str):
            component['distgit'] = distgit = {'name': distgit}

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
                distgit['branch'] = distgit.get('branch', self._distgit.get('branch', 'master'))

        for key in distgit:
            if key not in ['patches', 'src', 'name', 'tag', 'branch', 'freeze']:
                fatal("Unknown key {0} in component/distgit: {1}".format(key, component))

        self._ensure_key_or(component, 'pkgname', pkgname_default)

    def _load_overlay(self):     
        self.srcdir = self.workdir + '/src'
        self.mirror = GitMirror(self.srcdir)
        self.lookaside_mirror = self.srcdir + '/lookaside'

        ovlpath = self.workdir + '/overlay.yml'
        with open(ovlpath) as f:
            self._overlay = yaml.load(f)
        if os.path.islink(ovlpath):
            self._overlay_datadir = os.path.dirname(os.path.realpath(ovlpath))
        else:
            self._overlay_datadir = os.path.dirname(ovlpath)

        self._distgit = require_key(self._overlay, 'distgit')
        self._distgit_prefix = require_key(self._distgit, 'prefix')

    def _expand_overlay(self, fetchall=False, fetch=[],
                        parent_mirror=None):     
        expanded = copy.deepcopy(self._overlay)
        for component in expanded['components']:
            self._expand_component(component)
            ref = self._one_of_keys(component, 'freeze', 'branch', 'tag')
            do_fetch = fetchall or (component['name'] in fetch)
            src = component.get('src')
            if src is not None:
                revision = self.mirror.mirror(src, ref, fetch=do_fetch,
                                              parent_mirror=parent_mirror)
                component['revision'] = revision

            distgit = component.get('distgit')
            if distgit is not None:
                ref = self._one_of_keys(distgit, 'freeze', 'branch', 'tag')
                do_fetch = fetchall or (distgit['name'] in fetch)
                revision = self.mirror.mirror(distgit['src'], ref, fetch=do_fetch,
                                              parent_mirror=parent_mirror)
                distgit['revision'] = revision

        del expanded['aliases']
        expanded['00comment'] = 'Generated by rpmdistro-gitoverlay from overlay.yml: DO NOT EDIT!'

        return expanded

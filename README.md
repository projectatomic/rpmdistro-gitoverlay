# rpmdistro-gitoverlay

This is a tool to manage an "overlay" of packages on top of a base
distribution, where the upstream sources come from upstream git, the
spec files come from a "dist-git" system like Fedora uses, but the
spec files are automatically edited to point at git repository
commits.

The output is a single rpm-md/yum repository.

It is designed to be useful both for developers locally, as well as a
fully automated service.

<hr>

### Differences from COPR

A comparison with http://copr.fedoraproject.org/ is useful.  COPR
could be described as "a web UI on top of mockchain using OpenStack
for builds".  rpmdistro-gitoverlay is a command line tool that can
just uses raw mockchain, without involving virtualization.  This
means build inputs must currently be fully trusted.

 - COPR includes a web interface, a web API, authentication, etc.
   rpmdistro-gitoverlay is just a command line tool - you can
   use Buildbot/Jenkins/etc. to provide a UI.
 - COPR uses OpenStack, rpmdistro-gitoverlay requires you to
   "bring your own" virtualization for security.
 - COPR operates principally on source RPMs; you bring your
   own "git -> SRPM" solution.  rpmdistro-gitoverlay is
   a hardcoded "git -> SRPM" mechanism.
 - COPR is stateful; what is built is a function of the history of
   build invocations.  rpmdistro-gitoverlay takes as input a YAML
   file, and will synchronize state to it.  See below.

### State synchronization

rpmdistro-gitoverlay will attempt to continually synchronize state to
whatever is specified in the YAML file.

For example, at any point, a build administrator can choose an earlier
commit to build if the upstream breaks.  rpmdistro-gitoverlay will
rebuild the component with that earlier commit.

It will *not* automatically rebuild reverse dependencies like
[Nix](https://nixos.org/nix/) would, because it's not practical at
scale.  An update to glibc should not require rebuilding the entire
system.  At a higher level, "build purity" should not be the primary
goal of anyone shipping software.  The primary goal is functional,
high quality software, with fast continuous delivery.

A future version of rpmdistro-gitoverlay will support a mechanism to
optionally force reverse dependency rebuilds, as well as a rebuild of
everything.

Another example of rpmdistro-gitoverlay's anti-hysteresis is that if
you delete a source from the overlay, all RPMs generated from that
source will also drop out of the generated repository.

## An example overlay file

See [Example overlay](doc/example-overlay.yml) for an example.

## Running

Create a working directory where the primary data `src/` and `rpms/`
will be stored, and copy your `overlay.yml` in there (or symlink it to
a git checkout).  Then run `init`:

```
mkdir -p /srv/build
ln -s ~walters/src/fedora-atomic/overlay.yml .
rpmdistro-gitoverlay init
```

That finishes the one-time initialization work.  Now, we perform a
`resolve`: This will generate a `src/` directory which is a git mirror
of all inputs (recursively mirroring submodules), and take a snapshot
of exact commits into `snapshot.json`

```
rpmdistro-gitoverlay resolve --fetch-all
ls -al snapshot.json
```

Now, let's do a build:

```
rpmdistro-gitoverlay build
```

This will generate `rpms/`, which is a yum repository.  Note however
the system is idempotent, if we run again:

```
rpmdistro-gitoverlay build
```

Nothing should happen aside from a `createrepo` invocation.
    
### Other tools

The code in this project originated from
https://github.com/redhat-openstack/rdopkg as a baseline; however it
is (will become) rather different.

See also https://fedoraproject.org/wiki/Layered_build_scripts_for_package_maintainers
for a collection of other projects.


### Using this tool as a container

Both `podman` and `docker` are known to work with these instructions.

**Note**: Since this tool uses `mock` any time an image is run as a container it must
use `--privileged=true`.

#### Building

```
$ sudo podman build -t rdgo:latest `pwd`/packaging/
```

#### Using rpmdistro-gitoverlay
```
<cd to wherever you have an overlay.yml file you want to use>
$ sudo podman run --privileged=true -ti --rm -v `pwd`:/rdgo:z localhost/rdgo:latest init
[..]
$ sudo podman run --privileged=true -ti --rm -v `pwd`:/rdgo:z localhost/rdgo:latest resolve --fetch-all
[..]
$ sudo podman run --privileged=true -ti --rm -v `pwd`:/rdgo:z localhost/rdgo:latest build
[..]
```

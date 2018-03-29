This [rpmdistro-gitoverlay](https://github.com/cgwalters/rpmdistro-gitoverlay) project
is just one of [many projects like it](https://fedoraproject.org/wiki/Layered_build_scripts_for_package_maintainers).

But the transition to "manual integration" via Koji/dist-git etc. is painful.
What if Fedora primary release engineering actually worked this way?

Here's a series of steps we can take.

---

Remove the RPM `%changelog` from spec files
--

This is the first step. It's one of the two sources of guaranteed conflicts
across merges.  If we want to make PRs on dist-git useful, these conflict
sources need to be removed.

We could generate it from git commits and/or other sources of information
like upstream release git tags.

Create a production git mirror to augment/replace the lookaside cache
---

Rather than importing tarballs, mirror git repositories like rpmdistro-gitoverlay
does.  See also [git-evtag](https://github.com/cgwalters/git-evtag).

Teach koji (or "the build system") how to autogenerate Release
---

This is the other "guaranteed conflict" source with PRs on dist-git.  There's
a lot of implications to this; among other things the commit to dist git wouldn't
be quite the same as the SRPM.

Change the build/compose process to do x86_64 only first
---

The "compose" model as implemented by pungi has a lot of good ideas, but
it makes no sense to build everything on all architectures if systemd is broken
on all of them.  This is also true of Koji.  The "koji-shadow" or Debian "wanna-build"
style model where other achitectures "catch up" is significantly more scalable.

Release engineering ⇆ "QA" ⇆ development
---

People who are doing "QA" must have the ability to change how release
engineering works. A lot of developers understand their pain points and are in a
very good position to change release engineering to fix issues. And it makes no
sense for someone to do release engineering but *not* interact with testing
systems (and development).

*Rotate people* among focus on these roles, and blur the systems as much as possible.

Specifically in Fedora where "release engineering" makes sure the "compose" is
generated, and "QA" tests it. And it just sits there if it's known broken in
a fundamental way. There must be a *reaction* to tests failing on it. A simple
strawman is to have e.g. `compose/raw` and `compose/smoketested` etc. Like what
Bodhi does with `updates` and `updates-testing`.

Another example of a "reaction" to a test failure of course is to *revert* the broken
change.  That leads to:

Support reverting changes
---

`git revert && git push` should Just Work to revert a build.  Note that this
requires at least the "Koji autorelease" change.

Tell people using development streams to use `dnf distro-sync` and/or `rpm-ostree`.

Building a single RPM just a special case of multiple
---

This is what rpmdistro-gitoverlay implements.  One should be able to imagine
taking something like the YAML that exists today and define multiple of them, and
have them merge into a single repository.

See also [this post](https://lists.fedoraproject.org/archives/list/devel@lists.fedoraproject.org/message/QDEC4OJRQ3IPY3BDCDMCVQPOU4M4EYDD/).


Upstream source first, and embrace spec file generators
---

Like rpmdistro-gitoverlay, support finding a spec file in upstream git.
We should be *able* to override it downstream if needed.

Further, the only way to package language ecosystems (golang/Python/Rust) at
scale is to autogenerate spec files. There are tons of tools to generate spec
files, but where things fall over is that the generated result is committed to
git.

If we *start* from the upstream sources, then we can always generate a spec
file from it.

PRs-on-distgit
---

The focus of our testing and building should be on the "github style" model
of submitting a pull request, and having test systems be able to report into
it.

This would work a lot better if rather than having one git repository per
package, we had one or a series of layers.  See for example:

 - https://github.com/NixOS/nixpkgs
 - https://github.com/openembedded/openembedded-core
 - https://github.com/clearlinux/clr-bundles
 - https://github.com/coreos/coreos-overlay/

Blend upstream testing and downstream testing
---

In practice today, where CI exists at all, very very few upstream projects have
access to non-x86_64 architectures.  The first time then many things get
built or tested on e.g. `aarch64` will be when they hit Koji.

Koji should be changed to generate Kubernetes Jobs or equivalent; it shouldn't
be a cluster system itself.  This would lead naturally to having more freeform
CI style workflows that are also scheduled jobs in the cluster.

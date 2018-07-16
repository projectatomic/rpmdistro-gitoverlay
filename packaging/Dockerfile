FROM registry.fedoraproject.org/fedora:28
# We install fedpkg specifically because while it's optional, pretty much everyone
# will want it.
RUN dnf -y install autoconf automake dnf-utils fedpkg gcc git libtool make python2-pyyaml python3-PyYAML which && \
    dnf clean all && \
    adduser unprivileged && \
    usermod -a -G mock unprivileged && \
    git clone https://github.com/cgwalters/rpmdistro-gitoverlay && \
    cd rpmdistro-gitoverlay && \
    git checkout v2018.1 && \
    ./autogen.sh && \
    make && \
    make install

USER unprivileged
WORKDIR /rdgo
ENTRYPOINT ["/usr/local/bin/rpmdistro-gitoverlay"]

# Usage examples:
#  (Note we need --privileged since mock uses container functions internally)
#  alias rdgo='docker run -ti --rm --privileged -v $(pwd):/rdgo cgwalters/rpmdistro-gitoverlay'
#  rdgo init
#  rdgo resolve --fetch-all -b

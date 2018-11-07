FROM registry.fedoraproject.org/fedora:29
# We also add rsync since it's a common tool
RUN cd /etc/yum.repos.d && curl -L --remote-name-all https://copr.fedorainfracloud.org/coprs/walters/buildtools-fedora/repo/fedora-29/walters-buildtools-fedora-fedora-29.repo && \
    yum -y install rpmdistro-gitoverlay rsync && yum clean all && \
    adduser builder && usermod -a -G mock builder
USER builder
WORKDIR /srv
# Disabled for now since it breaks with Jenkins
# ENTRYPOINT ["/usr/bin/rpmdistro-gitoverlay"]

# Usage examples:
#  (Note we need --privileged since mock uses container functions internally)
#  alias rdgo='podman run -ti --rm --privileged -v $(pwd):/srv cgwalters/rpmdistro-gitoverlay'
#  rdgo init
#  rdgo resolve --fetch-all -b

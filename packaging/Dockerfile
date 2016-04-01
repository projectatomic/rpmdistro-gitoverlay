FROM centos
RUN cd /etc/yum.repos.d && \
    yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
    curl -L -O https://copr.fedorainfracloud.org/coprs/walters/buildtools/repo/epel-7/walters-buildtools-epel-7.repo && \
    yum -y install rpmdistro-gitoverlay && yum clean all && \
    adduser unprivileged && usermod -a -G mock unprivileged
USER unprivileged
WORKDIR /srv
ENTRYPOINT ["rpmdistro-gitoverlay"]


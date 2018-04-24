License:        BSD
Vendor:         Otus
Group:          PD01
URL:            http://otus.ru/lessons/3/
BuildRoot:      %{_tmppath}/otus-%{current_datetime}
Name:           ip2w
Version:        0.0.1
Release:        1
Source0:        otus-%{current_datetime}.tar.gz
BuildArch:      noarch
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
BuildRequires: systemd
Requires: python36u
Requires: python36u-pip
Requires: python36u-devel
Requires: uwsgi
Summary: ip to weather service


%description
Get weather by ip

Git version: %{git_version} (branch: %{git_branch})

%define __etcdir        /usr/local/etc/
%define __logdir        /var/log/ip2w/
%define __bindir        /usr/local/ip2w/
%define __systemddir    /usr/lib/systemd/system/

%prep
%setup -n otus-%{current_datetime}

%install
[ "%{buildroot}" != "/" ] && rm -fr %{buildroot}

%{__mkdir} -p %{buildroot}/%{__etcdir}
%{__mkdir} -p %{buildroot}/%{__logdir}
%{__mkdir} -p %{buildroot}/%{__bindir}
%{__mkdir} -p %{buildroot}/%{__systemddir}

%{__install} -pD -m 644 %{name}.service %{buildroot}/%{__systemddir}/%{name}.service
%{__install} -pD -m 755 %{name}.py %{buildroot}/%{__bindir}/%{name}.py
%{__install} -pD -m 644 %{name}.ini %{buildroot}/%{__etcdir}/%{name}.ini

%post
%systemd_post %{name}.service
systemctl daemon-reload

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun %{name}.service

%clean
[ "%{buildroot}" != "/" ] && rm -fr %{buildroot}


%files
%{__logdir}
%{__bindir}
%{__systemddir}
%{__etcdir}

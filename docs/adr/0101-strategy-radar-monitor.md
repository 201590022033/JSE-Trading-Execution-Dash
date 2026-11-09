# ADR 0101: Explicit local-evidence background monitor

A separate hidden worker is explicitly enabled and guarded by a SQLite lease. It reads retained watch/intraday evidence only, checks the reviewed JSE calendar, and durably records signal transitions with their traces. Source-unknown states do not trigger or rearm alerts. Windows notification submission is optional and remains distinct from proof of visible delivery. No provider, model or order call is made. No startup task is installed; an enabled-but-stopped worker is reported.


Optional Windows sign-in startup was subsequently added as an explicit opt-in. The control registers a named logon task when checked and requests removal on pause; mocked tests cover success and failure. It is not enabled by default and was not actually installed or verified through a Windows sign-out/sign-in in this check. Earlier statements in this document that no startup option exists describe the preceding state.

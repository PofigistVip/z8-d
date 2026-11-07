module z8.ldap.windows;

version (Windows):

import z8.runtime : IZ8LdapDirectory, IZ8LdapTransport, IZ8LdapProvider, Z8LdapDirectoryEntry,
    Z8LdapConfiguredProvider, z8_ldap_server_options, z8_ldap_set_provider;
import core.sys.windows.winldap;
import core.sys.windows.winber : BerElement, BerValue, ber_free, ber_bvfree;
import std.algorithm.searching : canFind;
import std.conv : to;
import std.string : fromStringz, indexOf;

pragma(lib, "wldap32.lib");

private void check(uint code, string operation) {
    if (code != LDAP_SUCCESS)
        throw new Exception("LDAP " ~ operation ~ " failed (" ~ code.to!string ~ ")");
}

private wchar[] terminated(wstring value) {
    if (value.canFind('\0')) throw new Exception("LDAP value contains a NUL character");
    return value.dup ~ '\0';
}

private struct Address { wstring host, base; uint port; bool secure; }
private Address parseAddress(wstring url) {
    import std.uri : decodeComponent;
    Address address;
    if (url.length >= 7 && url[0..7] == "ldap://"w) url = url[7..$];
    else if (url.length >= 8 && url[0..8] == "ldaps://"w) { url = url[8..$]; address.secure = true; }
    else throw new Exception("Expected an ldap:// or ldaps:// URL");
    if (!url.length || url.canFind('?') || url.canFind('#') || url.canFind('\0'))
        throw new Exception("Invalid LDAP server URL");
    auto slash = url.indexOf('/');
    if (slash >= 0) {
        address.base = decodeComponent(url[slash + 1 .. $].to!string).to!wstring;
        url = url[0 .. slash];
    }
    if (!url.length || url.canFind('@')) throw new Exception("Invalid LDAP server URL");
    size_t portStart = url.length;
    if (url[0] == '[') {
        auto end = url.indexOf(']');
        if (end <= 1) throw new Exception("Invalid LDAP server address");
        address.host = url[1..end];
        if (end + 1 < url.length) {
            if (url[end + 1] != ':') throw new Exception("Invalid LDAP server address");
            portStart = end + 2;
        }
    } else {
        auto colon = url.indexOf(':');
        if (colon >= 0) { address.host = url[0..colon]; portStart = colon + 1; }
        else address.host = url;
    }
    address.port = address.secure ? 636 : 389;
    if (portStart < url.length) {
        auto port = url[portStart..$];
        foreach (c; port) if (c < '0' || c > '9') throw new Exception("Invalid LDAP server port");
        address.port = port.to!uint;
        if (!address.port || address.port > 65535) throw new Exception("Invalid LDAP server port");
    } else if (url[$-1] == ':') throw new Exception("Invalid LDAP server port");
    if (!address.host.length) throw new Exception("Invalid LDAP server address");
    return address;
}

/// Register after loading server.properties; settings are captured at registration.
IZ8LdapProvider z8_windows_ldap_configure() {
    auto options = z8_ldap_server_options();
    if (options.connectTimeoutMilliseconds < 0 || options.pageSize < 0)
        throw new Exception("LDAP timeout and page size must be nonnegative");
    return z8_ldap_set_provider(new Z8LdapConfiguredProvider(
        new Z8WindowsLdapTransport(cast(uint)options.connectTimeoutMilliseconds, options.sslTrusted), options.pageSize));
}

// WinLDAP calls this per connection only when the host explicitly enables the
// same trust-all behavior as Java's TrustedSSLSocketFactory.
private extern(C) ubyte acceptServerCertificate(LDAP* connection, void** certificate) nothrow @nogc { return 1; }

/// A connection is bound with LDAP simple authentication; ldaps:// uses TLS.
class Z8WindowsLdapTransport : IZ8LdapTransport {
    private uint timeoutMilliseconds;
    private bool sslTrusted;
    this(uint timeoutMilliseconds = 3000, bool sslTrusted = false) {
        this.timeoutMilliseconds = timeoutMilliseconds; this.sslTrusted = sslTrusted;
    }
    IZ8LdapDirectory connect(wstring url, wstring principal, wstring credentials) {
        // JNDI accepts a whitespace-separated list of provider URLs and
        // proceeds to the next server when a connection or bind fails.
        bool whitespace(wchar c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }
        size_t start;
        Exception last;
        while (start < url.length) {
            while (start < url.length && whitespace(url[start])) ++start;
            if (start == url.length) break;
            size_t end = start;
            while (end < url.length && !whitespace(url[end])) ++end;
            try { return connectOne(url[start .. end], principal, credentials); }
            catch (Exception error) { last = error; }
            start = end;
        }
        if (last !is null) throw last;
        throw new Exception("Expected an ldap:// or ldaps:// URL");
    }
    private IZ8LdapDirectory connectOne(wstring url, wstring principal, wstring credentials) {
        auto address = parseAddress(url);
        auto host = terminated(address.host);
        auto handle = address.secure ? ldap_sslinitW(host.ptr, address.port, 1) : ldap_initW(host.ptr, address.port);
        if (handle is null) throw new Exception("LDAP initialization failed");
        scope(failure) ldap_unbind_s(handle);
        uint protocolVersion = LDAP_VERSION3;
        check(ldap_set_optionW(handle, LDAP_OPT_PROTOCOL_VERSION, &protocolVersion), "set protocol version");
        if (address.secure && sslTrusted)
            check(ldap_set_optionW(handle, LDAP_OPT_SERVER_CERTIFICATE, cast(void*)&acceptServerCertificate), "set TLS certificate policy");
        LDAP_TIMEVAL timeout;
        timeout.tv_sec = cast(int)(timeoutMilliseconds / 1000);
        timeout.tv_usec = cast(int)((timeoutMilliseconds % 1000) * 1000);
        check(ldap_connect(handle, timeoutMilliseconds ? &timeout : null), "connect");
        auto user = terminated(principal), password = terminated(credentials);
        scope(exit) password[] = '\0';
        check(ldap_simple_bind_sW(handle, user.ptr, password.ptr), "bind");
        return new WindowsLdapDirectory(handle, address.base);
    }
}

private class WindowsLdapDirectory : IZ8LdapDirectory {
    private LDAP* handle;
    private wstring base;
    this(LDAP* handle, wstring base) { this.handle = handle; this.base = base; }
    bool isOpen() { return handle !is null; }
    void close() {
        if (handle !is null) { auto old = handle; handle = null; check(ldap_unbind_s(old), "unbind"); }
    }
    Z8LdapDirectoryEntry[] search(wstring searchBase, wstring searchFilter, int pageSize) {
        if (handle is null) throw new Exception("LDAP connection is closed");
        if (pageSize < 0) throw new Exception("Invalid LDAP page size");
        auto fullBase = searchBase;
        if (base.length) fullBase = fullBase.length ? fullBase ~ ","w ~ base : base;
        auto searchRoot = terminated(fullBase), filter = terminated(searchFilter);
        Z8LdapDirectoryEntry[] entries;
        BerValue* cookie;
        scope(exit) if (cookie !is null) ber_bvfree(cookie);
        do {
            LDAPControlW* control;
            scope(exit) if (control !is null) ldap_control_freeW(control);
            LDAPControlW*[2] controls;
            if (pageSize) {
                check(ldap_create_page_controlW(handle, cast(uint)pageSize, cookie, 1, &control), "create page control");
                controls[0] = control;
            }
            LDAPMessage* result;
            scope(exit) if (result !is null) ldap_msgfree(result);
            check(ldap_search_ext_sW(handle, searchRoot.ptr, LDAP_SCOPE_SUBTREE, filter.ptr, null, 0,
                pageSize ? controls.ptr : null, null, null, 0, &result), "search");
            for (auto entry = ldap_first_entry(handle, result); entry !is null; entry = ldap_next_entry(handle, entry)) {
                auto item = new Z8LdapDirectoryEntry();
                auto dn = ldap_get_dnW(handle, entry);
                if (dn is null) throw new Exception("LDAP entry has no distinguished name");
                item.distinguishedName = dn.fromStringz.idup;
                ldap_memfreeW(dn);
                BerElement* position;
                scope(exit) if (position !is null) ber_free(position, 0);
                auto attribute = ldap_first_attributeW(handle, entry, &position);
                while (attribute !is null) {
                    auto current = attribute;
                    scope(exit) ldap_memfreeW(current);
                    auto values = ldap_get_valuesW(handle, entry, attribute);
                    wstring[] list;
                    if (values !is null) {
                        scope(exit) ldap_value_freeW(values);
                        for (size_t i = 0; values[i] !is null; ++i) list ~= values[i].fromStringz.idup;
                    }
                    item.attributes[attribute.fromStringz.idup] = list;
                    attribute = ldap_next_attributeW(handle, entry, position);
                }
                entries ~= item;
            }
            if (!pageSize) break;
            LDAPControlW** response;
            scope(exit) if (response !is null) ldap_controls_freeW(response);
            check(ldap_parse_resultW(handle, result, null, null, null, null, &response, 0), "parse result");
            if (cookie !is null) { ber_bvfree(cookie); cookie = null; }
            uint total;
            check(ldap_parse_page_controlW(handle, response, &total, &cookie), "parse page control");
        } while (cookie !is null && cookie.bv_len);
        return entries;
    }
}

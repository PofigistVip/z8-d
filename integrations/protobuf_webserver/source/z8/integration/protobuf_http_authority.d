module z8.integration.protobuf_http_authority;

import std.conv : to;
import z8.runtime : Z8ApplicationSession, Z8Guid, IZ8UserChangeNotifier, IZ8RoleChangeNotifier;
import z8.webserver.civetweb : IZ8HttpAuthority, IZ8HttpSessionLogout, Z8HttpRequest;
import z8.authority.messages : Z8AuthorityLogin, Z8AuthorityAuthorize, Z8AuthorityLogout;
import z8.authority.service : IZ8AuthorityEndpoint, IZ8AuthorityLogout;
import z8.protobuf.wire : Z8ProtobufException;

// Each HTTP authorization consults the supplied remote authority endpoint.
class Z8ProtobufHttpAuthority : IZ8HttpAuthority, IZ8HttpSessionLogout, IZ8UserChangeNotifier, IZ8RoleChangeNotifier {
    private IZ8AuthorityEndpoint endpoint;
    private wstring schema;
    this(IZ8AuthorityEndpoint endpoint, wstring schema) {
        if (endpoint is null || schema is null || !schema.length) throw new Z8ProtobufException("authority endpoint and schema are required");
        this.endpoint = endpoint; this.schema = schema.idup;
    }
    Z8ApplicationSession authorize(Z8HttpRequest request, wstring id, wstring server) {
        if (id is null || !id.length) return null;
        return endpoint.authorize(Z8AuthorityAuthorize(id, schema, server));
    }
    Z8ApplicationSession login(Z8HttpRequest request, wstring login, wstring password) {
        if (login is null || !login.length || password is null) return null;
        auto address = request is null || request.remoteAddress is null ? null : request.remoteAddress.to!wstring;
        return endpoint.login(Z8AuthorityLogin(login, password, schema, address));
    }
    void logoutSession(Z8HttpRequest request, wstring id) {
        auto logout = cast(IZ8AuthorityLogout)endpoint;
        if (logout is null) throw new Z8ProtobufException("authority does not support logout");
        logout.logout(Z8AuthorityLogout(id, schema));
    }
    void userChanged(Z8Guid id, wstring schema) { endpoint.userChanged(id, schema); }
    void roleChanged(Z8Guid id, wstring schema) { endpoint.roleChanged(id, schema); }
}

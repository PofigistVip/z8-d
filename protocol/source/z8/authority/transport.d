module z8.authority.transport;

// The embedding application supplies an authenticated RPC transport.
enum Z8AuthorityMethod { login = 1, authorize = 2, userChanged = 3, roleChanged = 4, applyUserChanged = 5, applyRoleChanged = 6 }
interface IZ8AuthorityRpcTransport {
    ubyte[] call(Z8AuthorityMethod method, const(ubyte)[] payload);
}

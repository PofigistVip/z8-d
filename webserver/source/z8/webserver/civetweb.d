module z8.webserver.civetweb;

import core.memory : GC;
import core.thread : Thread, thread_attachThis, thread_detachThis;
import std.algorithm : min;
import std.conv : to;
import std.json : JSONValue;
import std.string : fromStringz, toStringz, indexOf, startsWith, toLower;
import z8.runtime;

// The declarations below follow the pinned CivetWeb 1.16 public C header.
extern(C) {
    private struct MgContext;
    private struct MgConnection;
    private struct MgRequestInfo {
        const(char)* requestMethod;
        const(char)* requestUri;
        const(char)* localUriRaw;
        const(char)* localUri;
        const(char)* httpVersion;
        const(char)* queryString;
        const(char)* remoteUser;
        char[48] remoteAddress;
        long contentLength;
        int remotePort, serverPort, isSsl;
    }
    private struct MgServerPort { int protocol, port, isSsl, isRedirect, reserved1, reserved2, reserved3, reserved4; }
    private MgContext* mg_start(const(void)* callbacks, void* userData, const(char)** options);
    private void mg_stop(MgContext* context);
    private alias MgHandler = int function(MgConnection* connection, void* data) nothrow;
    private void mg_set_request_handler(MgContext* context, const(char)* uri, MgHandler callback, void* data);
    private const(MgRequestInfo)* mg_get_request_info(const(MgConnection)* connection);
    private const(char)* mg_get_header(const(MgConnection)* connection, const(char)* name);
    private int mg_get_server_ports(const(MgContext)* context, int size, MgServerPort* ports);
    private int mg_read(MgConnection* connection, void* data, size_t length);
    private int mg_write(MgConnection* connection, const(void)* data, size_t length);
    private void rt_moduleTlsCtor();
    private void rt_moduleTlsDtor();
}

class Z8HttpRequest {
    string method, path, query, contentType, remoteAddress;
    ubyte[] body;
}
private class BadRequest : Exception { this(string text) { super(text); } }
private class BodyTooLarge : Exception { this() { super("request body too large"); } }
private class UnsupportedMedia : Exception { this() { super("multipart requests are not implemented"); } }

private string cString(const(char)* value) { return value is null ? "" : value.fromStringz.idup; }
private int hexDigit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    throw new BadRequest("invalid form escape");
}
private wstring decodeForm(string source) {
    char[] bytes;
    for (size_t i; i < source.length; ++i) {
        if (source[i] == '+') bytes ~= ' ';
        else if (source[i] == '%') {
            if (i + 2 >= source.length) throw new BadRequest("invalid form escape");
            bytes ~= cast(char)((hexDigit(source[i + 1]) << 4) | hexDigit(source[i + 2])); i += 2;
        } else bytes ~= source[i];
    }
    try { return z8_string_new(bytes.length ? (cast(string)bytes).to!wstring : ""w); }
    catch (Exception) { throw new BadRequest("invalid UTF-8 in form data"); }
}
private void addParameters(Z8StringMap parameters, string encoded) {
    size_t start;
    while (start < encoded.length) {
        auto end = encoded.indexOf('&', start);
        auto stop = end < 0 ? encoded.length : cast(size_t)end;
        auto item = encoded[start .. stop];
        auto equal = item.indexOf('=');
        auto key = decodeForm(equal < 0 ? item : item[0 .. equal]);
        auto value = decodeForm(equal < 0 ? "" : item[equal + 1 .. $]);
        if (!parameters.z8_containsKey(key)) parameters.z8_add(key, value);
        if (end < 0) break;
        start = stop + 1;
    }
}
private void writeAll(MgConnection* connection, string data) {
    size_t offset;
    while (offset < data.length) {
        auto count = mg_write(connection, data.ptr + offset, data.length - offset);
        if (count <= 0) return;
        offset += count;
    }
}
private int respond(MgConnection* connection, int status, string description, string body) {
    auto header = "HTTP/1.1 " ~ status.to!string ~ " " ~ description ~ "\r\n" ~
        "Content-Type: application/json; charset=UTF-8\r\nConnection: close\r\nContent-Length: " ~
        body.length.to!string ~ "\r\n\r\n";
    writeAll(connection, header); writeAll(connection, body);
    return status;
}
private ubyte[] readBody(MgConnection* connection, long length, bool chunked, size_t limit) {
    if (length > 0 && cast(ulong)length > limit) throw new BodyTooLarge();
    if (length < 0 && !chunked) return null;
    ubyte[] result;
    ubyte[8192] buffer;
    while (length < 0 || result.length < cast(ulong)length) {
        auto remaining = length < 0 ? buffer.length : min(buffer.length, cast(size_t)length - result.length);
        auto count = mg_read(connection, buffer.ptr, remaining);
        if (count < 0) throw new BadRequest("request read failed");
        if (!count) { if (length >= 0) throw new BadRequest("incomplete request body"); break; }
        if (cast(size_t)count > limit - result.length) throw new BodyTooLarge();
        result ~= buffer[0 .. count];
    }
    return result;
}

class Z8CivetServer {
    private MgContext* context;
    private void delegate(Z8HttpRequest request) handler;
    private size_t bodyLimit;

    this(string listening, void delegate(Z8HttpRequest request) handler, size_t bodyLimit = 1024 * 1024) {
        if (handler is null) throw new Exception("HTTP request handler is required");
        if (!bodyLimit) throw new Exception("HTTP body limit must be positive");
        this.handler = handler; this.bodyLimit = bodyLimit;
        const(char)*[7] options = ["listening_ports\0".ptr, listening.toStringz,
            "num_threads\0".ptr, "4\0".ptr, "enable_keep_alive\0".ptr, "no\0".ptr, null];
        GC.setAttr(cast(void*)this, GC.BlkAttr.NO_MOVE);
        GC.addRoot(cast(void*)this);
        context = mg_start(null, null, options.ptr);
        if (context is null) { GC.removeRoot(cast(void*)this); throw new Exception("CivetWeb could not start"); }
        mg_set_request_handler(context, "/\0".ptr, &dispatch, cast(void*)this);
    }
    int port() {
        if (context is null) throw new Exception("CivetWeb server is stopped");
        MgServerPort[1] ports;
        if (mg_get_server_ports(context, 1, ports.ptr) != 1) throw new Exception("cannot read server port");
        return ports[0].port;
    }
    void stop() {
        if (context is null) return;
        mg_stop(context); context = null;
        GC.removeRoot(cast(void*)this);
    }
    private int handle(MgConnection* connection) {
        try {
            auto info = mg_get_request_info(connection);
            if (info is null) throw new BadRequest("missing request information");
            auto request = new Z8HttpRequest();
            request.method = cString(info.requestMethod); request.path = cString(info.localUri);
            request.query = cString(info.queryString); request.remoteAddress = cString(info.remoteAddress.ptr);
            request.contentType = cString(mg_get_header(connection, "Content-Type\0".ptr));
            auto transfer = cString(mg_get_header(connection, "Transfer-Encoding\0".ptr)).toLower();
            request.body = readBody(connection, info.contentLength, transfer == "chunked", bodyLimit);
            auto type = request.contentType.toLower();
            if (type.startsWith("multipart/form-data")) throw new UnsupportedMedia();
            auto application = new Z8ApplicationRequest();
            addParameters(application.parameters, request.query);
            if (type.startsWith("application/x-www-form-urlencoded")) addParameters(application.parameters, cast(string)request.body);
            application.parameters.z8_add("ip"w, request.remoteAddress.to!wstring);
            auto previous = z8_application_set_request(application);
            scope (exit) z8_application_set_request(previous);
            handler(request);
            return respond(connection, 200, "OK", z8_application_response_text(application).to!string);
        } catch (Z8Redirect redirect) {
            JSONValue[string] data;
            data["request"] = JSONValue.init; data["success"] = JSONValue(false);
            data["status"] = JSONValue(302); data["redirect"] = JSONValue(redirect.location.to!string);
            return respond(connection, 302, "Found", JSONValue(data).toString());
        } catch (BodyTooLarge) { return respond(connection, 413, "Content Too Large", `{"error":"request body too large"}`); }
        catch (UnsupportedMedia) { return respond(connection, 415, "Unsupported Media Type", `{"error":"unsupported media type"}`); }
        catch (BadRequest) { return respond(connection, 400, "Bad Request", `{"error":"invalid request"}`); }
        catch (Throwable) { return respond(connection, 500, "Internal Server Error", `{"error":"internal server error"}`); }
    }
}
private extern(C) int dispatch(MgConnection* connection, void* data) nothrow {
    bool attached;
    try {
        attached = Thread.getThis() !is null;
        if (!attached) {
            thread_attachThis();
            try { rt_moduleTlsCtor(); }
            catch (Throwable error) { thread_detachThis(); throw error; }
        }
        scope (exit) if (!attached) { rt_moduleTlsDtor(); thread_detachThis(); }
        return (cast(Z8CivetServer)data).handle(connection);
    } catch (Throwable) { return 500; }
}

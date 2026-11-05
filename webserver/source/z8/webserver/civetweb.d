module z8.webserver.civetweb;

import core.memory : GC;
import core.internal.gc.proxy : gc_getProxy;
import core.thread : Thread, thread_attachThis, thread_detachThis;
import std.algorithm : min;
import std.conv : to;
import std.json : JSONValue, parseJSON;
import std.string : fromStringz, toStringz, indexOf, startsWith, toLower, split;
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
    private struct MgCallbacks {
        void*[15] unused;
        void* function(const(MgContext)*, int) nothrow initThread;
        void function(const(MgContext)*, int, void*) nothrow exitThread;
        void* initConnection;
    }
    private MgContext* mg_start(const(MgCallbacks)* callbacks, void* userData, const(char)** options);
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
    private void thread_setThis(void* thread) nothrow @nogc;
}

class Z8HttpRequest {
    string method, path, query, contentType, remoteAddress, host, forwardedAddress;
    ubyte[] body;
    Z8RequestMonitor monitor;
}
private class BadRequest : Exception { this(string text) { super(text); } }
private class BodyTooLarge : Exception { this() { super("request body too large"); } }

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
// Split header parameters while preserving quoted semicolons and escaped quotes.
private string[string] headerParameters(string header, out string kind) {
    import std.string : strip;
    string[string] result;
    size_t i;
    while (i < header.length && header[i] != ';') ++i;
    kind = header[0 .. i].strip.toLower();
    while (i < header.length) {
        ++i;
        while (i < header.length && (header[i] == ' ' || header[i] == '\t')) ++i;
        auto start = i;
        while (i < header.length && header[i] != '=' && header[i] != ';') ++i;
        if (i == header.length || header[i] != '=') throw new BadRequest("invalid header parameter");
        auto key = header[start .. i].strip.toLower();
        if (!key.length) throw new BadRequest("empty header parameter");
        ++i;
        while (i < header.length && (header[i] == ' ' || header[i] == '\t')) ++i;
        string value;
        if (i < header.length && header[i] == '"') {
            ++i;
            char[] decoded;
            bool closed;
            while (i < header.length) {
                char c = header[i++];
                if (c == '"') { closed = true; break; }
                if (c == '\\') { if (i == header.length) throw new BadRequest("invalid quoted header"); c = header[i++]; }
                decoded ~= c;
            }
            if (!closed) throw new BadRequest("unterminated quoted header");
            value = decoded.idup;
            while (i < header.length && (header[i] == ' ' || header[i] == '\t')) ++i;
            if (i < header.length && header[i] != ';') throw new BadRequest("invalid quoted header");
        } else {
            start = i;
            while (i < header.length && header[i] != ';') ++i;
            value = header[start .. i].strip;
        }
        result[key] = value;
    }
    return result;
}
private wstring multipartText(string value) {
    try { return z8_string_new(value.length ? value.to!wstring : ""w); }
    catch (Exception) { throw new BadRequest("invalid UTF-8 in multipart data"); }
}
private ptrdiff_t findBytes(const(ubyte)[] data, string needle, size_t start) {
    if (start > data.length || needle.length > data.length - start) return -1;
    foreach (i; start .. data.length - needle.length + 1)
        if (data[i .. i + needle.length] == cast(const(ubyte)[])needle) return cast(ptrdiff_t)i;
    return -1;
}
private void addMultipart(Z8ApplicationRequest application, string contentType, const(ubyte)[] data) {
    string kind;
    auto attributes = headerParameters(contentType, kind);
    auto boundary = "boundary" in attributes;
    if (boundary is null || !boundary.length || boundary.length > 70) throw new BadRequest("invalid multipart boundary");
    foreach (c; *boundary) if (c < 32 || c >= 127) throw new BadRequest("invalid multipart boundary");
    auto delimiter = "--" ~ *boundary;
    if (data.length < delimiter.length || data[0 .. delimiter.length] != cast(const(ubyte)[])delimiter)
        throw new BadRequest("missing multipart boundary");
    size_t pos = delimiter.length;
    for (;;) {
        if (pos + 2 > data.length) throw new BadRequest("incomplete multipart boundary");
        if (data[pos .. pos + 2] == cast(const(ubyte)[])"--") {
            pos += 2;
            if (pos != data.length && (pos + 2 > data.length || data[pos .. pos + 2] != cast(const(ubyte)[])"\r\n"))
                throw new BadRequest("invalid final multipart boundary");
            return;
        }
        if (data[pos .. pos + 2] != cast(const(ubyte)[])"\r\n") throw new BadRequest("invalid multipart boundary");
        pos += 2;
        auto headerEnd = findBytes(data, "\r\n\r\n", pos);
        if (headerEnd < 0) throw new BadRequest("missing multipart headers");
        auto headers = cast(string)data[pos .. headerEnd];
        string disposition;
        foreach (line; headers.split("\r\n")) {
            auto colon = line.indexOf(':');
            if (colon <= 0) throw new BadRequest("invalid multipart header");
            import std.string : strip;
            if (line[0 .. colon].strip.toLower() == "content-disposition") {
                if (disposition.length) throw new BadRequest("duplicate content disposition");
                disposition = line[colon + 1 .. $].strip;
            }
        }
        auto part = headerParameters(disposition, kind);
        auto name = "name" in part;
        if (kind != "form-data" || name is null) throw new BadRequest("invalid content disposition");
        pos = cast(size_t)headerEnd + 4;
        auto marker = "\r\n" ~ delimiter;
        ptrdiff_t end;
        for (;;) {
            end = findBytes(data, marker, pos);
            if (end < 0) throw new BadRequest("missing closing multipart boundary");
            auto after = cast(size_t)end + marker.length;
            if (after + 2 <= data.length && (data[after .. after + 2] == cast(const(ubyte)[])"\r\n" ||
                    data[after .. after + 2] == cast(const(ubyte)[])"--")) break;
            pos = cast(size_t)end + 2;
        }
        // Search may have skipped boundary-like bytes; content begins after headers.
        auto contentStart = cast(size_t)headerEnd + 4;
        auto content = data[contentStart .. cast(size_t)end];
        auto filename = "filename" in part;
        if (filename !is null) application.files.z8_add(z8_file_from_upload(multipartText(*filename), content));
        else application.parameters.z8_add(multipartText(*name), multipartText(cast(string)content));
        pos = cast(size_t)end + marker.length;
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

enum Z8ResponseMode { raw, application }
// A host-provided authority decides whether credentials or a session are valid.
// Implementations must support concurrent calls; returning null denies access.
interface IZ8HttpAuthority {
    Z8ApplicationSession authorize(Z8HttpRequest request, wstring sessionId, wstring serverId);
    Z8ApplicationSession login(Z8HttpRequest request, wstring login, wstring password);
}
class Z8CivetServer {
    private MgContext* context;
    private void delegate(Z8HttpRequest request) handler;
    private size_t bodyLimit;
    private Z8ResponseMode responseMode;
    private wstring serverId;
    private IZ8HttpAuthority authority;
    private wstring accessDeniedMessage;

    this(string listening, void delegate(Z8HttpRequest request) handler, size_t bodyLimit = 1024 * 1024,
         Z8ResponseMode responseMode = Z8ResponseMode.raw, wstring serverId = null,
         IZ8HttpAuthority authority = null, wstring accessDeniedMessage = "Incorrect login or password"w,
         string documentRoot = null, string requestPath = "/") {
        import std.file : isDir;
        import std.path : absolutePath;
        if (handler is null) throw new Exception("HTTP request handler is required");
        if (!bodyLimit) throw new Exception("HTTP body limit must be positive");
        if (!requestPath.startsWith("/") || requestPath.indexOf('?') >= 0 || requestPath.indexOf('#') >= 0)
            throw new Exception("invalid request path");
        if (documentRoot.length) {
            if (requestPath == "/") throw new Exception("static files require a specific request path");
            documentRoot = absolutePath(documentRoot);
            if (!isDir(documentRoot)) throw new Exception("static document root is not a directory");
        }
        this.handler = handler; this.bodyLimit = bodyLimit; this.responseMode = responseMode; this.serverId = serverId;
        this.authority = authority; this.accessDeniedMessage = accessDeniedMessage;
        const(char)*[] options = ["listening_ports\0".ptr, listening.toStringz,
            "num_threads\0".ptr, "4\0".ptr, "enable_keep_alive\0".ptr, "no\0".ptr];
        if (documentRoot.length) options ~= ["document_root\0".ptr, documentRoot.toStringz,
            "enable_directory_listing\0".ptr, "no\0".ptr,
            "ssi_pattern\0".ptr, "\0".ptr,
            "hide_files_patterns\0".ptr, "**/WEB-INF/**|**/META-INF/**|**/.git/**|**/.env$\0".ptr];
        options ~= null;
        GC.setAttr(cast(void*)this, GC.BlkAttr.NO_MOVE);
        GC.addRoot(cast(void*)this);
        MgCallbacks callbacks;
        callbacks.initThread = &initWorker; callbacks.exitThread = &exitWorker;
        context = mg_start(&callbacks, null, options.ptr);
        if (context is null) { GC.removeRoot(cast(void*)this); throw new Exception("CivetWeb could not start"); }
        mg_set_request_handler(context, requestPath.toStringz, &dispatch, cast(void*)this);
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
            request.host = cString(mg_get_header(connection, "Host\0".ptr));
            request.forwardedAddress = cString(mg_get_header(connection, "X-Real-IP\0".ptr));
            auto transfer = cString(mg_get_header(connection, "Transfer-Encoding\0".ptr)).toLower();
            request.body = readBody(connection, info.contentLength, transfer == "chunked", bodyLimit);
            auto type = request.contentType.toLower();
            auto application = new Z8ApplicationRequest();
            request.monitor = new Z8RequestMonitor();
            application.monitor = request.monitor;
            if (type.startsWith("multipart/form-data")) addMultipart(application, request.contentType, request.body);
            else {
                addParameters(application.parameters, request.query);
                if (type.startsWith("application/x-www-form-urlencoded")) addParameters(application.parameters, cast(string)request.body);
            }
            application.parameters.z8_add("ip"w, request.remoteAddress.to!wstring);
            auto requestId = application.parameters.z8_get("request"w);
            if (authority !is null) {
                auto sessionId = application.parameters.z8_get("session"w);
                if (sessionId !is null)
                    application.session = authority.authorize(request, sessionId, application.parameters.z8_get("server"w));
                if (application.session is null && requestId == "login"w) {
                    auto login = application.parameters.z8_get("login"w);
                    auto password = application.parameters.z8_get("password"w);
                    if (login !is null) application.session = authority.login(request, login, password is null ? ""w : password);
                }
                if (application.session is null) {
                    auto monitor = new Z8RequestMonitor();
                    monitor.message(Z8MonitorLevel.error, accessDeniedMessage);
                    JSONValue[string] denied;
                    denied["request"] = JSONValue.init; denied["success"] = JSONValue(false);
                    denied["status"] = JSONValue(401); denied["info"] = parseJSON(monitor.infoJson().to!string);
                    denied["data"] = JSONValue(cast(JSONValue[])[]);
                    return respond(connection, 401, "Unauthorized", JSONValue(denied).toString());
                }
            }
            auto previous = z8_application_set_request(application);
            scope (exit) z8_application_set_request(previous);
            if (responseMode == Z8ResponseMode.application) z8_application_start_response(application, requestId);
            try {
                handler(request);
                if (responseMode == Z8ResponseMode.application)
                    z8_application_finish_response(application, request.monitor, serverId);
            } catch (Z8Redirect redirect) { throw redirect; }
            catch (Throwable error) {
                if (responseMode == Z8ResponseMode.raw) throw error;
                auto message = error.msg.length ? error.msg.to!wstring : "Internal server error."w;
                request.monitor.message(Z8MonitorLevel.error, message);
                return respond(connection, 200, "OK", z8_application_error_response(requestId, request.monitor, serverId).to!string);
            }
            return respond(connection, 200, "OK", z8_application_response_text(application).to!string);
        } catch (Z8Redirect redirect) {
            JSONValue[string] data;
            data["request"] = JSONValue.init; data["success"] = JSONValue(false);
            data["status"] = JSONValue(302); data["redirect"] = JSONValue(redirect.location.to!string);
            return respond(connection, 302, "Found", JSONValue(data).toString());
        } catch (BodyTooLarge) { return respond(connection, 413, "Content Too Large", `{"error":"request body too large"}`); }
        catch (BadRequest) { return respond(connection, 400, "Bad Request", `{"error":"invalid request"}`); }
        catch (Throwable) { return respond(connection, 500, "Internal Server Error", `{"error":"internal server error"}`); }
    }
}
private extern(C) void* initWorker(const(MgContext)* context, int type) nothrow {
    if (type != 1) return null;
    try {
        thread_attachThis();
        try { rt_moduleTlsCtor(); }
        catch (Throwable error) { thread_detachThis(); thread_setThis(null); throw error; }
        return cast(void*)1;
    } catch (Throwable) { return null; }
}
private extern(C) void exitWorker(const(MgContext)* context, int type, void* initialized) nothrow {
    if (type != 1 || initialized is null) return;
    try { rt_moduleTlsDtor(); } catch (Throwable) { }
    gc_getProxy().cleanupThread(Thread.getThis());
    thread_detachThis();
    thread_setThis(null);
}
private extern(C) int dispatch(MgConnection* connection, void* data) nothrow {
    if (Thread.getThis() is null) return 500;
    try { return (cast(Z8CivetServer)data).handle(connection); }
    catch (Throwable) { return 500; }
}

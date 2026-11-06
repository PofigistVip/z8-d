module z8.database.scheduler_logs;

import std.conv : to;
import z8.runtime;

// Host-owned storage for a scheduled job's log. Implementations may be called
// concurrently by independent schedulers.
interface IZ8SchedulerLogStore {
    Z8File writeLog(wstring schema, wstring jobName, Z8MonitorEntry[] entries);
}

// Files are created under an explicitly configured root. Names are sanitized
// and include stable schema/job hashes and a unique file identifier.
class Z8FileSchedulerLogStore : IZ8SchedulerLogStore {
    private string root;
    this(string root) {
        import std.path : absolutePath;
        if (root is null || !root.length) throw new Exception("scheduler log root is required");
        this.root = absolutePath(root);
    }
    private string component(wstring value, string prefix) {
        auto name = value is null ? ""w : value;
        string result = prefix ~ "-";
        foreach (wchar c; name) {
            if (result.length >= prefix.length + 65) break;
            result ~= (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' ? cast(char)c : '_';
        }
        return result ~ "-" ~ z8_guid_to_string(z8_guid_create_name(name)).to!string[0 .. 8];
    }
    Z8File writeLog(wstring schema, wstring jobName, Z8MonitorEntry[] entries) {
        import std.path : buildPath;
        wstring contents;
        foreach (entry; entries) {
            wstring level;
            final switch (entry.level) {
                case Z8MonitorLevel.info: level = "INFO"w; break;
                case Z8MonitorLevel.warning: level = "WARNING"w; break;
                case Z8MonitorLevel.error: level = "ERROR"w; break;
            }
            contents ~= level ~ ": ["w ~ (entry.time is null ? ""w : z8_date_toString(entry.time)) ~ "] "w ~
                (entry.text is null ? ""w : entry.text) ~ "\r\n"w;
        }
        auto path = buildPath(root, component(schema, "schema"), component(jobName, "job"),
            z8_guid_to_string(z8_guid_create_random()).to!string ~ ".log");
        auto file = z8_file_from_path(path.to!wstring);
        return z8_file_write(file, contents);
    }
}
